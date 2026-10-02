from pathlib import Path
root=Path(__file__).resolve().parent
html=(root/'src/index.template.html').read_text(encoding='utf-8')
for marker,filename in [('/* STYLE */','style.css'),('/* VISUAL_STYLE */','visual.css'),('/* LEARNING_STYLE */','learning.css'),('<!-- LEARNING_SECTION -->','learning_section.html'),('<!-- VISUAL_SECTION -->','visual_section.html'),('/* HARDWARE_STYLE */','hardware.css'),('<!-- HARDWARE_SECTION -->','hardware_section.html'),('/* HARDWARE_CORE */','hardware_core.js'),('/* HARDWARE_UI */','hardware_ui.js'),('/* CORE */','core.js'),('/* WEBGL */','webgl_rover.js'),('/* APP */','app.js'),('/* VISUAL */','visual.js'),('/* LEARNING */','learning.js')]:
    content=(root/'src'/filename).read_text(encoding='utf-8')
    assert marker in html, marker
    html=html.replace(marker,content)
output=root/'ROVER_Real_Hardware_Studio.html'
output.write_text(html,encoding='utf-8')
print(output)
