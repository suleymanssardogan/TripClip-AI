import "@testing-library/jest-dom/vitest";

// jsdom, gerçek bir layout engine olmadığı için Element.prototype.scrollIntoView
// UYGULAMIYOR — harita↔liste senkronizasyonu (OptimizerResult.tsx) bunu
// seçili durağı görünüme kaydırmak için çağırıyor. Standart jsdom-test stub'ı.
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
