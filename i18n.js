(function (global) {
  const STORAGE_KEY = "portfolio-lang";
  const DEFAULT_LANG = "de";
  const SUPPORTED = ["de", "en", "fr"];

  const I18n = {
    lang: DEFAULT_LANG,
    messages: {},

    async init() {
      const saved = localStorage.getItem(STORAGE_KEY);
      const initial = SUPPORTED.includes(saved) ? saved : DEFAULT_LANG;
      await this.setLanguage(initial, { skipApply: true });
      return this;
    },

    async setLanguage(lang, options) {
      if (!SUPPORTED.includes(lang)) {
        return;
      }

      if (!this.messages[lang]) {
        const response = await fetch(`locales/${lang}.json`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error("Locale not found: " + lang);
        }
        this.messages[lang] = await response.json();
      }

      this.lang = lang;
      localStorage.setItem(STORAGE_KEY, lang);
      document.documentElement.lang = lang;

      if (!options?.skipApply) {
        this.apply();
      }
    },

    t(key, vars) {
      const parts = key.split(".");
      let value = this.messages[this.lang];
      for (const part of parts) {
        value = value?.[part];
      }
      if (value == null) {
        return key;
      }
      if (!vars) {
        return String(value);
      }
      return String(value).replace(/\{\{(\w+)\}\}/g, (_, name) =>
        vars[name] != null ? String(vars[name]) : ""
      );
    },

    pickLocalized(value) {
      if (value && typeof value === "object" && !Array.isArray(value)) {
        return (
          value[this.lang] ||
          value.de ||
          value.en ||
          value.fr ||
          ""
        );
      }
      return String(value || "");
    },

    apply() {
      document.querySelectorAll("[data-i18n]").forEach((element) => {
        const key = element.getAttribute("data-i18n");
        if (!key) return;
        element.textContent = this.t(key);
      });

      document.querySelectorAll("[data-i18n-title]").forEach((element) => {
        const key = element.getAttribute("data-i18n-title");
        if (!key) return;
        document.title = this.t(key);
      });

      document.querySelectorAll("[data-i18n-aria]").forEach((element) => {
        const key = element.getAttribute("data-i18n-aria");
        if (!key) return;
        element.setAttribute("aria-label", this.t(key));
      });

      document.querySelectorAll(".lang-switch__btn").forEach((button) => {
        if (!(button instanceof HTMLButtonElement)) return;
        const isActive = button.dataset.lang === this.lang;
        button.classList.toggle("lang-switch__btn--active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      });
    },
  };

  global.I18n = I18n;
})(window);
