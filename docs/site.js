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
  function showView(key) {
    const view = views[key];
    for (const item of controls.querySelectorAll("button"))
      item.setAttribute("aria-pressed", String(item.dataset.view === key));
    const img = document.getElementById("preview-image");
    img.src = `img/${key}.png`;
    img.alt = view.alt;
    document.getElementById("preview-title").textContent = view.title;
    document.getElementById("preview-description").textContent =
      view.description;
    document.getElementById("preview-file").textContent = view.file;
    document.getElementById("preview-link").href = view.href;
  }
  controls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-view]");
    if (button) showView(button.dataset.view);
  });

  // One pinned product story, not a fake scrollbar or a wheel interceptor.
  if (window.gsap && window.ScrollTrigger) {
    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();
    media.add(
      "(min-width: 1024px) and (min-height: 760px) and (prefers-reduced-motion: no-preference)",
      () => {
        // Enlarged text needs natural document flow, not a viewport-sized stage.
        if (
          parseFloat(getComputedStyle(document.documentElement).fontSize) > 20
        )
          return;
        const section = document.getElementById("explorar");
        const stage = section.querySelector(".scroll-stage");
        section.classList.add("scroll-story");
        const keys = Object.keys(views);
        let phase = -1;
        keys.forEach((key) => {
          const image = new Image();
          image.src = `img/${key}.png`;
        });
        ScrollTrigger.create({
          trigger: section,
          pin: stage,
          start: "top top",
          end: () => "+=" + innerHeight * 2.4,
          invalidateOnRefresh: true,
          anticipatePin: 1,
          onUpdate(self) {
            stage.style.setProperty("--story-progress", self.progress);
            const next = Math.min(3, Math.floor(self.progress * 4));
            if (next !== phase) {
              phase = next;
              showView(keys[next]);
              gsap.fromTo(
                "#preview-image",
                { opacity: 0.5, y: 12 },
                { opacity: 1, y: 0, duration: 0.45, overwrite: true },
              );
            }
          },
        });
        gsap.to(".hero-grid", {
          y: -32,
          opacity: 0.65,
          ease: "none",
          scrollTrigger: {
            trigger: ".hero",
            start: "top top",
            end: "bottom top",
            scrub: 0.6,
          },
        });
        document.fonts.ready.then(() => ScrollTrigger.refresh());
        return () => {
          section.classList.remove("scroll-story");
          stage.style.removeProperty("--story-progress");
          showView("recorrido");
        };
      },
    );
    new MutationObserver(() => {
      if (parseFloat(getComputedStyle(document.documentElement).fontSize) > 20)
        media.revert();
    }).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["style"],
    });
  }

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
