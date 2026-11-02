# Changelog

## 2026-11-02 — presentación de Atlify 1.1

Publicación inicial en GitHub. La versión del skill es 1.1.0; no se crea un tag automáticamente.

### Presentación

- Landing editorial con la identidad de Miguel: verde bosque, Archivo y fuentes locales.
- Explorador de cuatro capturas reales, enlaces profundos a la demo y descarga offline.
- Instalación separada del prompt de uso, con selector de agente y copiar accesible.
- FAQ de alcance, privacidad, permisos para compartir código y límites de validación.
- Portada Open Graph 1200×630 y kit de texto para LinkedIn y portfolio.

### Calidad de publicación

- Regeneración de demos desde el fixture y chequeo de vigencia sin modificar archivos.
- Timestamp gzip estable y comparación del código descomprimido entre runtimes.
- Pruebas de assets, metadatos, enlaces, navegación, teclado, texto al 200%, sin JS y sin red.
- CI de Python 3.10/3.13 y navegador Chromium, sin despliegue automático.

### Base 1.1 ya preparada en el checkout

- `--actualizar` como flag real; resolución de endpoint por sufijo e IDs canónicos.
- Inventario breve con `extract --routes`; descubrimiento de tests con lista vacía.
- Contrato del skill en inglés, visor en español con tema claro/oscuro.
- Instalador multiagente con enlaces o copias y desinstalación propia.

Los hallazgos del agente y su rendimiento no se infieren de los tests de scripts.

### Experiencia de scroll

- Escena del atlas fijada en escritorio con GSAP ScrollTrigger, cuatro capítulos
  vinculados al avance y transiciones suaves, sin scroll-jacking.
- Entrada/salida más continua y separadores menos marcados, conservando la marca.
- Flujo nativo en móvil y movimiento reducido, con librerías alojadas localmente.
