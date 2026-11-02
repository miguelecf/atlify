/* Progressive enhancement: the content and demo links work without JavaScript. */
(() => {
  const views = {
    recorrido: {
      title: "Seguí el pedido, no veinte pestañas.",
      description:
        "Cada paso muestra qué hace, dónde vive y qué código lo resuelve. Las preguntas te ayudan a leer con criterio.",
      alt: "Recorrido de GET /api/appointments: pasos entre frontend, backend y tabla con el código real.",
      file: "atlas.html",
      href: "demo/atlas.html#/endpoint/GET%20%2Fapi%2Fappointments/recorrido?paso=3",
    },
    mapa: {
      title: "Ubicá las piezas antes de leerlas.",
      description:
        "Frontend, backend y base de datos en una misma vista. Seleccioná un endpoint en la demo para seguir sus conexiones.",
      alt: "Mapa de pet-care-api con las conexiones del endpoint GET /api/appointments entre las tres capas.",
      file: "atlas.html",
      href: "demo/atlas.html#/mapa?sel=e%3AGET%20%2Fapi%2Fappointments",
    },
    hallazgos: {
      title: "Un problema, con su evidencia al lado.",
      description:
        "Severidad, archivo, símbolo y escenario de fallo. El agente propone un arreglo mínimo; vos decidís qué hacer.",
      alt: "Hallazgos del repo de ejemplo clasificados por severidad, con un problema y su código desplegados.",
      file: "atlas.html",
      href: "demo/atlas.html#/hallazgos",
    },
    foco: {
      title: "Un cambio chico también tiene vecinos.",
      description:
        "El modo endpoint reúne funciones compartidas, tablas y referencias a tests. Revisá el impacto antes de editar.",
      alt: "Modo Antes de tocarlo para GET /api/appointments, con funciones y tablas compartidas y referencias a tests.",
      file: "atlas-get-api-appointments.html",
      href: "demo/foco.html",
    },
  };
  const controls = document.querySelector(".explorer-controls");
  controls.hidden = false;
  controls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-view]");
    if (!button) return;
    const view = views[button.dataset.view];
    for (const item of controls.querySelectorAll("button"))
      item.setAttribute("aria-pressed", String(item === button));
    const img = document.getElementById("preview-image");
    img.src = `img/${button.dataset.view}.png`;
    img.alt = view.alt;
    document.getElementById("preview-title").textContent = view.title;
    document.getElementById("preview-description").textContent =
      view.description;
    document.getElementById("preview-file").textContent = view.file;
    document.getElementById("preview-link").href = view.href;
  });

  const picker = document.querySelector(".agent-picker");
  picker.hidden = false;
  const prompts = {
    codex: ["Codex", "$atlify"],
    claude: ["Claude Code", "/atlify"],
    other: ["otro agente", "Usá atlify para generar el atlas de este repo."],
  };
  picker.addEventListener("change", () => {
    const [name, prompt] = prompts[picker.querySelector(":checked").value];
    document.getElementById("usage-label").textContent = `Mensaje para ${name}`;
    document.querySelector("#code-usage code").textContent = prompt;
    document
      .querySelector("#code-usage")
      .closest(".code-block")
      .querySelector("[data-status]").textContent = "";
  });

  for (const button of document.querySelectorAll("[data-copy]")) {
    button.hidden = false;
    button.addEventListener("click", async () => {
      const target = document.getElementById(button.dataset.copy);
      const status = button
        .closest(".code-block")
        .querySelector("[data-status]");
      try {
        await navigator.clipboard.writeText(target.textContent.trim());
        status.textContent = "Copiado al portapapeles.";
      } catch {
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(target);
        selection.removeAllRanges();
        selection.addRange(range);
        status.textContent =
          "No se pudo copiar automáticamente. El texto quedó seleccionado: usá Ctrl+C o ⌘C.";
      }
    });
  }
})();
