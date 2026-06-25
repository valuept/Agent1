// Deterministic seeded RNG so the demo data is stable across reloads.
(function () {
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const rand = mulberry32(42);
  const pick = (arr) => arr[Math.floor(rand() * arr.length)];

  const services = [
    "auth-api", "billing-svc", "checkout", "search-index", "notify-worker",
    "user-profile", "payments-gw", "recommend-ml", "cdn-edge", "analytics-pipe",
  ];
  const authors = ["a.khan", "m.rossi", "j.smith", "l.nguyen", "p.dubois", "s.weber", "t.ito", "r.garcia"];
  const teams = ["Platform", "Payments", "Growth", "Data", "Infra"];
  const risks = ["low", "low", "low", "medium", "medium", "high"];
  const outcomes = ["success", "success", "success", "success", "partial", "rolled"];

  const N = 260;
  const today = new Date(2026, 5, 11); // matches session date
  const records = [];
  for (let i = 0; i < N; i++) {
    const daysAgo = Math.floor(rand() * 90);
    const d = new Date(today);
    d.setDate(d.getDate() - daysAgo);
    const risk = pick(risks);
    // High risk skews toward worse outcomes.
    let outcome = pick(outcomes);
    if (risk === "high" && rand() < 0.4) outcome = pick(["partial", "rolled", "rolled"]);
    if (risk === "low" && rand() < 0.5) outcome = "success";
    records.push({
      id: "CHG-" + (10000 + i),
      date: d.toISOString().slice(0, 10),
      _daysAgo: daysAgo,
      service: pick(services),
      author: pick(authors),
      team: pick(teams),
      risk,
      outcome,
    });
  }
  records.sort((a, b) => (a.date < b.date ? 1 : -1));

  window.DASHBOARD_DATA = { records, teams, services, today: today.toISOString().slice(0, 10) };
})();
