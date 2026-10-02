/* Project-local adapter for the official SysML Pilot kernel libraries.
 * This adapter calls Xtext/EMF APIs; it does not infer validity from console text.
 */
import com.google.gson.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.emf.ecore.EReference;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.xtext.diagnostics.Severity;
import org.eclipse.xtext.nodemodel.INode;
import org.eclipse.xtext.nodemodel.util.NodeModelUtils;
import org.eclipse.xtext.resource.IResourceServiceProvider;
import org.eclipse.xtext.util.CancelIndicator;
import org.eclipse.xtext.validation.CheckMode;
import org.eclipse.xtext.validation.IResourceValidator;
import org.eclipse.xtext.validation.Issue;
import org.omg.sysml.interactive.SysMLInteractive;
import org.omg.sysml.lang.sysml.Element;

public final class SysMLHeadless {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().serializeNulls().create();

    private static JsonObject diagnostic(Issue issue, Resource resource) {
        JsonObject result = new JsonObject();
        result.addProperty("severity", issue.getSeverity().name());
        result.addProperty("code", issue.getCode());
        result.addProperty("message", issue.getMessage());
        result.addProperty("file", resource.getURI().toFileString());
        result.addProperty("uri", issue.getUriToProblem() == null ? null : issue.getUriToProblem().toString());
        result.addProperty("line", issue.getLineNumber());
        result.addProperty("column", issue.getColumn());
        result.addProperty("offset", issue.getOffset());
        result.addProperty("length", issue.getLength());
        result.addProperty("syntax_error", issue.isSyntaxError());
        return result;
    }

    private static JsonObject adapterError(String code, String message) {
        JsonObject result = new JsonObject();
        result.addProperty("severity", "ERROR");
        result.addProperty("code", code);
        result.addProperty("message", message);
        result.addProperty("origin", "adapter");
        return result;
    }

    private static JsonObject elementSummary(Element element, Resource resource) {
        JsonObject result = new JsonObject();
        result.addProperty("element_id", element.getElementId());
        result.addProperty("type", element.eClass().getName());
        result.addProperty("declared_name", element.getDeclaredName());
        result.addProperty("qualified_name", element.getQualifiedName());
        result.addProperty("source_file", resource.getURI().toFileString());
        INode node = NodeModelUtils.getNode(element);
        result.addProperty("explicit_source_node", node != null);
        if (node != null) {
            result.addProperty("line", node.getStartLine());
            result.addProperty("end_line", node.getEndLine());
            result.addProperty("offset", node.getOffset());
            result.addProperty("length", node.getLength());
        }
        JsonObject references = new JsonObject();
        // One level only: preserve resolved names for external standard-library elements
        // such as FeatureReferenceExpression.referent -> SI::W. Never recursively expand.
        for (EReference reference : element.eClass().getEAllReferences()) {
            if (reference.isContainment()) continue;
            Object value = element.eGet(reference, true);
            if (reference.isMany()) {
                JsonArray targets = new JsonArray();
                if (value instanceof Iterable<?> values) {
                    for (Object target : values) if (target instanceof Element targetElement)
                        targets.add(referenceSummary(targetElement));
                }
                references.add(reference.getName(), targets);
            } else if (value instanceof Element targetElement) {
                references.add(reference.getName(), referenceSummary(targetElement));
            } else {
                references.add(reference.getName(), JsonNull.INSTANCE);
            }
        }
        result.add("references", references);
        return result;
    }

    private static JsonObject referenceSummary(Element element) {
        JsonObject result = new JsonObject();
        result.addProperty("element_id", element.getElementId());
        result.addProperty("type", element.eClass().getName());
        result.addProperty("qualified_name", element.getQualifiedName());
        result.addProperty("name", element.getName());
        result.addProperty("declared_name", element.getDeclaredName());
        result.addProperty("is_proxy", element.eIsProxy());
        return result;
    }

    private static void write(Path path, JsonElement data) throws Exception {
        Files.writeString(path, GSON.toJson(data) + "\n", StandardCharsets.UTF_8);
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Expected request.json path");
        JsonObject request = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        Path output = Path.of(request.get("output_dir").getAsString());
        Files.createDirectories(output);
        JsonObject result = new JsonObject();
        JsonArray diagnostics = new JsonArray();
        result.add("diagnostics", diagnostics);
        result.addProperty("adapter", "official-pilot-xtext-emf");
        result.addProperty("status", "ERROR");
        result.add("model_json_path", JsonNull.INSTANCE);
        result.addProperty("library_path", request.get("library_path").getAsString());
        result.addProperty("package_name", request.get("package_name").getAsString());
        long started = System.nanoTime();
        int exit = 3;
        try {
            SysMLInteractive interactive = SysMLInteractive.createInstance();
            interactive.setVerbose(false);
            interactive.loadLibrary(request.get("library_path").getAsString());
            List<Resource> inputs = new ArrayList<>();
            // Load/index every file before resolving references. Input order is not a dependency order.
            for (JsonElement file : request.getAsJsonArray("model_files")) {
                Resource resource = interactive.readResource(file.getAsString());
                interactive.addInputResource(resource);
                inputs.add(resource);
            }
            interactive.resolveAllInputResources();
            boolean errors = false;
            for (Resource resource : inputs) {
                IResourceValidator validator = IResourceServiceProvider.Registry.INSTANCE
                    .getResourceServiceProvider(resource.getURI()).getResourceValidator();
                for (Issue issue : validator.validate(resource, CheckMode.ALL, CancelIndicator.NullImpl)) {
                    diagnostics.add(diagnostic(issue, resource));
                    if (issue.getSeverity() == Severity.ERROR) errors = true;
                }
            }
            result.addProperty("input_resource_count", inputs.size());
            result.addProperty("library_resource_count", interactive.getLibraryResources().size());
            if (errors) {
                result.addProperty("status", "FAIL");
                exit = 2;
            } else {
                String packageName = request.get("package_name").getAsString();
                Element requested = interactive.resolve(packageName);
                if (requested == null || requested.eIsProxy() || !interactive.isInputResource(requested.eResource())) {
                    diagnostics.add(adapterError("PACKAGE_NOT_FOUND", "Requested package is not an element of the supplied input files: " + packageName));
                    result.addProperty("status", "FAIL");
                    exit = 2;
                } else {
                    Object exported = interactive.export(packageName, Collections.emptyList());
                    if (!(exported instanceof JsonElement json)) {
                        throw new IllegalStateException("Official export returned non-JSON: " + exported);
                    }
                    Path modelPath = output.resolve("model.json");
                    write(modelPath, json);
                    result.addProperty("model_json_path", modelPath.toString());
                    result.addProperty("model_format", "official SysML API model delta from JsonElementProcessingFacade");
                    JsonArray elements = new JsonArray();
                    for (Resource resource : inputs) {
                        List<Element> parsedElements = new ArrayList<>();
                        Iterator<EObject> all = resource.getAllContents();
                        while (all.hasNext()) {
                            EObject object = all.next();
                            if (object instanceof Element element) parsedElements.add(element);
                        }
                        for (Element element : parsedElements) elements.add(elementSummary(element, resource));
                    }
                    Path astPath = output.resolve("ast-elements.json");
                    write(astPath, elements);
                    result.addProperty("ast_json_path", astPath.toString());
                    result.addProperty("ast_element_count", elements.size());
                    result.addProperty("status", "PASS");
                    exit = 0;
                }
            }
        } catch (Throwable error) {
            error.printStackTrace(System.err);
            diagnostics.add(adapterError("TOOL_EXCEPTION", error.getClass().getName() + ": " + error.getMessage()));
            result.addProperty("status", "ERROR");
        } finally {
            result.addProperty("elapsed_ms", (System.nanoTime() - started) / 1_000_000);
            write(output.resolve("result.json"), result);
        }
        System.exit(exit);
    }
}
