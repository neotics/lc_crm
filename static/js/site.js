document.addEventListener("DOMContentLoaded", () => {
  animateCounters();
  animateProgressBars();
  setupReveal();
  setupSearchFilters();
  setupTabs();
  setupCommands();
  setupRiskFilter();
});

function animateCounters() {
  document.querySelectorAll("[data-count-to]").forEach((element) => {
    const target = parseCountValue(element.dataset.countTo);
    if (!Number.isFinite(target)) {
      element.textContent = "0";
      return;
    }
    const duration = 900;
    const start = performance.now();
    const decimals = Number.isInteger(target) ? 0 : getDecimalPlaces(element.dataset.countTo);

    function tick(now) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const currentValue = target * eased;
      const value = decimals === 0 ? Math.round(currentValue) : currentValue.toFixed(decimals);
      element.textContent = value;
      if (progress < 1) {
        requestAnimationFrame(tick);
      }
    }

    requestAnimationFrame(tick);
  });
}

function parseCountValue(rawValue) {
  if (typeof rawValue !== "string") return 0;
  const normalized = rawValue
    .trim()
    .replace(/\s+/g, "")
    .replace(/,(?=\d{3}(?:\D|$))/g, "")
    .replace(/,/g, ".");
  return Number(normalized || 0);
}

function getDecimalPlaces(rawValue) {
  if (typeof rawValue !== "string") return 0;
  const normalized = rawValue.trim().replace(/\s+/g, "").replace(/,(?=\d{3}(?:\D|$))/g, "");
  const separator = Math.max(normalized.lastIndexOf("."), normalized.lastIndexOf(","));
  return separator === -1 ? 0 : normalized.length - separator - 1;
}

function animateProgressBars() {
  document.querySelectorAll(".progress > span[data-width]").forEach((bar) => {
    const width = `${bar.dataset.width}%`;
    bar.style.width = "0%";
    requestAnimationFrame(() => {
      bar.style.width = width;
    });
  });

  document.querySelectorAll(".chart-fill[data-width]").forEach((bar) => {
    const width = `${bar.dataset.width}%`;
    bar.style.width = "0%";
    requestAnimationFrame(() => {
      bar.style.width = width;
    });
  });
}

function setupReveal() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  document.querySelectorAll(".reveal").forEach((element) => observer.observe(element));
}

function setupSearchFilters() {
  document.querySelectorAll("[data-search-input]").forEach((input) => {
    input.addEventListener("input", () => {
      const target = document.querySelector(input.dataset.searchInput);
      if (!target) return;
      const term = input.value.trim().toLowerCase();
      target.querySelectorAll("[data-search-row]").forEach((row) => {
        const haystack = row.dataset.searchRow.toLowerCase();
        row.hidden = !haystack.includes(term);
      });
    });
  });
}

function setupRiskFilter() {
  document.querySelectorAll("[data-risk-target]").forEach((group) => {
    group.querySelectorAll("[data-risk-value]").forEach((button) => {
      button.addEventListener("click", () => {
        group.querySelectorAll("[data-risk-value]").forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        const value = button.dataset.riskValue;
        const target = document.querySelector(group.dataset.riskTarget);
        if (!target) return;
        target.querySelectorAll("[data-risk-row]").forEach((row) => {
          row.hidden = value !== "all" && row.dataset.riskRow !== value;
        });
      });
    });
  });
}

function setupTabs() {
  document.querySelectorAll("[data-tabs]").forEach((container) => {
    const buttons = container.querySelectorAll("[data-tab-button]");
    const panels = document.querySelectorAll(container.dataset.tabs);

    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const targetId = button.dataset.tabButton;
        buttons.forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        panels.forEach((panel) => {
          panel.hidden = panel.id !== targetId;
        });
      });
    });
  });
}

function setupCommands() {
  document.querySelectorAll("[data-command]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.command === "toggle-sidebar") {
        document.body.classList.toggle("sidebar-collapsed");
      }
      if (button.dataset.command === "toggle-theme") {
        const html = document.documentElement;
        const currentTheme = html.dataset.theme === "dark" ? "dark" : "light";
        const nextTheme = currentTheme === "dark" ? "light" : "dark";
        html.dataset.theme = nextTheme;
        document.cookie = `site_theme=${nextTheme}; path=/; max-age=31536000`;
        button.textContent = nextTheme === "dark" ? button.dataset.labelDark : button.dataset.labelLight;
      }
      if (button.dataset.command === "spotlight") {
        const input = document.querySelector("[data-global-focus]");
        if (input) {
          input.focus();
          input.select?.();
        }
      }
    });
  });
}
