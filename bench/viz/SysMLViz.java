/* Draw a SysML v2 model with the official Pilot's own visualizer (the %viz command of its Jupyter kernel).
 * Reads a request JSON: library_path, model_files, names (elements to draw), views, styles, output_svg and
 * optionally output_png and graphviz_dot. Writes the SVG, the Pilot's PlantUML text and a result JSON next to it.
 * The Pilot is asked for PlantUML text (style PUMLCODE) and PlantUML lays it out with Graphviz dot when
 * graphviz_dot points to one, else with its built-in Java port of dot (Smetana), which cannot place ports on
 * nested parts, so interconnection views come out unreadable. Run with -Djava.awt.headless=true: PlantUML
 * measures text with AWT.
 */
import com.google.gson.*;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import net.sourceforge.plantuml.FileFormat;
import net.sourceforge.plantuml.FileFormatOption;
import net.sourceforge.plantuml.SourceStringReader;
import org.eclipse.emf.ecore.resource.Resource;
import org.omg.sysml.interactive.SysMLInteractive;
import org.omg.sysml.interactive.VizResult;

public final class SysMLViz {
    private static List<String> strings(JsonObject request, String key) {
        List<String> out = new ArrayList<>();
        if (request.has(key)) for (JsonElement item : request.getAsJsonArray(key)) out.add(item.getAsString());
        return out;
    }

    public static void main(String[] args) throws Exception {
        JsonObject request = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        Path svgPath = Path.of(request.get("output_svg").getAsString());
        JsonObject result = new JsonObject();
        result.addProperty("status", "ERROR");
        long started = System.nanoTime();
        int exit = 3;
        try {
            SysMLInteractive interactive = SysMLInteractive.createInstance();
            interactive.setVerbose(false);
            interactive.loadLibrary(request.get("library_path").getAsString());
            for (String file : strings(request, "model_files")) {
                Resource resource = interactive.readResource(file);
                interactive.addInputResource(resource);
            }
            interactive.resolveAllInputResources();
            List<String> styles = strings(request, "styles");
            if (!styles.contains("PUMLCODE")) styles.add("PUMLCODE");
            VizResult viz = interactive.viz(strings(request, "names"), strings(request, "views"), styles, List.of());
            if (viz.hasException()) {
                result.addProperty("message", viz.formatException());
                exit = 2;
            } else {
                String plantuml = viz.getPlantUML();
                if (plantuml == null) throw new IllegalStateException("The Pilot returned no PlantUML text: " + viz);
                String dot = request.has("graphviz_dot") ? request.get("graphviz_dot").getAsString() : null;
                boolean graphviz = dot != null && Files.isExecutable(Path.of(dot));
                if (graphviz) System.setProperty("GRAPHVIZ_DOT", dot);
                String laidOut = graphviz ? plantuml : plantuml.replaceFirst("@startuml[^\\n]*\\n", "$0!pragma layout smetana\n");
                result.addProperty("layout", graphviz ? "graphviz" : "smetana");
                ByteArrayOutputStream svg = new ByteArrayOutputStream();
                new SourceStringReader(laidOut).outputImage(svg, new FileFormatOption(FileFormat.SVG));
                Files.createDirectories(svgPath.getParent());
                Files.write(svgPath, svg.toByteArray());
                Files.writeString(Path.of(svgPath.toString().replaceAll("\\.svg$", "") + ".puml"), plantuml, StandardCharsets.UTF_8);
                if (request.has("output_png")) {
                    ByteArrayOutputStream png = new ByteArrayOutputStream();
                    new SourceStringReader(laidOut).outputImage(png, new FileFormatOption(FileFormat.PNG));
                    Files.write(Path.of(request.get("output_png").getAsString()), png.toByteArray());
                }
                result.addProperty("status", "OK");
                result.addProperty("svg", svgPath.toString());
                exit = 0;
            }
        } catch (Throwable error) {
            error.printStackTrace(System.err);
            result.addProperty("message", error.getClass().getName() + ": " + error.getMessage());
        } finally {
            result.addProperty("elapsed_ms", (System.nanoTime() - started) / 1_000_000);
            Files.writeString(Path.of(svgPath.toString().replaceAll("\\.svg$", "") + ".json"),
                new GsonBuilder().setPrettyPrinting().create().toJson(result) + "\n", StandardCharsets.UTF_8);
        }
        System.exit(exit);
    }
}
