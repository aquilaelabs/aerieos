// The page's questions: one modal for every one of them,
// in place of the browser's confirm and prompt, whose OK and
// Cancel said yes and no for questions that had other answers ("OK copies
// it, Cancel leaves it" was the storage move's). The house dialog
// (a-dialog): `.modal > .box`, its h3 the question, what follows it in
// `.field` bands, the foot's verbs in words, the primary first and anything
// destructive last; Escape and a press on the backdrop are Cancel.
//
// When one is asked, and how many: a press asks
// only when its yes costs something (it deletes or overwrites, cuts off
// someone's work, or grants more reach), and at most once: what a press
// needs a yes for is gathered first and listed in one question, as `parts`.
// On a phone a question is a sheet at the foot of the screen, as tall as its
// words (page-components.css, .modal.askdlg), where every other dialog is
// the whole screen; one that asks for a line of text sits at the top, clear
// of the keyboard.
//
// One classic script beside index.html (docs/design-language.md, Files):
// pure declarations, nothing runs at load.

"use strict";

let askSeq = 0;

// ask({title, text, choices, cancel}): the value of the choice pressed, or
// null for Cancel, Escape or the backdrop. `choices` are [{label, value,
// danger}], the first the primary; `title` defaults to the text's first
// paragraph, the rest being its body. `field` asks for a line of text as
// well ({value, label}), and the answer is then {value, text}. `parts` are
// what the one yes covers, [{head, lines}], each a short heading over its
// lines, drawn under the text.
function ask({title = "", text = "", choices = [{label: "Yes", value: true}], cancel = "Cancel", field = null, parts = []} = {}){
  parts = (parts || []).filter(p => p && (p.lines || []).length);
  const paras = String(text || "").split(/\n\s*\n/).map(p => p.trim()).filter(Boolean);
  // The title is the question alone, up to its first "?" (the operator, 23
  // Oct: a whole message as the title read as shouting); what follows it in
  // that paragraph leads the body.
  let head = title;
  if (!head){
    const at = askQuestion(paras);
    head = at.question;
    paras.splice(0, paras.length, ...at.rest);
  }
  const danger = choices.some(c => c.danger);
  return new Promise(resolve => {
    const id = `ask${++askSeq}`;
    const m = document.createElement("div");
    m.className = "modal askdlg" + (field ? " typed" : "");
    m.setAttribute("role", "dialog");
    m.setAttribute("aria-modal", "true");
    m.setAttribute("aria-labelledby", `${id}T`);
    m.hidden = true;
    const btn = (c, i) => `<button type="button" data-ai="${i}" class="${
      [i === 0 && !c.danger && !c.caution ? "primary" : "", c.danger ? "danger" : c.caution ? "caution" : ""].filter(Boolean).join(" ")}">${esc(c.label)}</button>`;
    const cancelBtn = cancel === null ? "" : `<button type="button" data-acancel>${esc(cancel)}</button>`;
    // The primary first and anything destructive last: a question whose
    // answer destroys something puts Cancel before it.
    const verbs = choices.map(btn).join("");
    drawHTML(m, `<div class="box">
      <h3 id="${id}T">${esc(head)}</h3>
      ${paras.map(p => `<div class="field"><p class="asksaid">${esc(p).replace(/\n/g, "<br>")}</p></div>`).join("")}
      ${parts.map(p => `<div class="field askpart"><label>${esc(p.head)}</label><ul class="asksaid">${
        p.lines.map(l => `<li>${esc(l)}</li>`).join("")}</ul></div>`).join("")}
      ${field ? `<div class="field">${field.label ? `<label for="${id}F">${esc(field.label)}</label>` : ""}
        <input id="${id}F" data-afield value="${esc(field.value || "")}" spellcheck="false" autocomplete="off"
          aria-label="${esc(field.label || head)}"></div>` : ""}
      <div class="foot"><span class="sp"></span>${danger ? cancelBtn + verbs : verbs + cancelBtn}</div>
    </div>`);
    document.body.appendChild(m);
    armModal(m);
    let over = false;
    const done = v => {
      if (over) return;
      over = true;
      m.hidden = true;
      setTimeout(() => m.remove(), 400);
      resolve(v);
    };
    const value = i => field ? {value: choices[i].value, text: m.querySelector("[data-afield]").value} : choices[i].value;
    // A press on the backdrop is Cancel, and so is Escape, which the
    // page's one dialog keydown (modalKeys) sends here as a backdrop press.
    m.onclick = e => { if (e.target === m) done(null); };
    const cancelBack = m.querySelector("[data-acancel]");
    if (cancelBack) cancelBack.onclick = () => done(null);
    m.querySelectorAll("[data-ai]").forEach(b => b.onclick = () => done(value(+b.dataset.ai)));
    if (field) m.querySelector("[data-afield]").onkeydown = e => {
      if (e.key === "Enter"){ e.preventDefault(); done(value(0)); }
    };
    m.hidden = false;
    requestAnimationFrame(() => (field ? m.querySelector("[data-afield]") : m.querySelector(danger ? "[data-acancel]" : '[data-ai="0"]'))?.focus());
    // The test harness answers a question as it answered the browser's
    // (lib.mjs): it is told the words and says which button to press, a
    // choice's index or -1 for Cancel, and the press is made on the modal.
    if (typeof window.__bbAsk === "function"){
      // ...the parts as words after the text, a heading then its lines.
      const said = [String(text || ""), ...parts.map(p => `${p.head}:\n${p.lines.map(l => "\u2022 " + l).join("\n")}`)].filter(Boolean).join("\n\n");
      Promise.resolve(window.__bbAsk({title: head, text: said, choices: choices.map(c => c.label)}))
        .then(i => requestAnimationFrame(() => {
          if (field && typeof i === "object" && i){ m.querySelector("[data-afield]").value = i.text ?? ""; i = i.index ?? 0; }
          const b = i === -1 || i === null ? m.querySelector("[data-acancel]") : m.querySelector(`[data-ai="${i ?? 0}"]`);
          (b || m.querySelector("[data-acancel]"))?.click();
        }));
    }
  });
}

// A question's text split into its title and the rest (the operator, 23
// Oct): the title is the question sentence, wherever it sits, from the
// sentence before it ends to its "?"; the words before and after it, in
// their order, are the body. A text with no question is its own first
// paragraph as the title.
function askQuestion(paras){
  const i = paras.findIndex(p => p.includes("?"));
  if (i < 0) return {question: paras[0] || "", rest: paras.slice(1)};
  const p = paras[i], q = p.indexOf("?");
  const lead = p.slice(0, q).lastIndexOf(". ");
  const start = lead < 0 ? 0 : lead + 2;
  let question = p.slice(start, q + 1).trim();
  question = question.charAt(0).toUpperCase() + question.slice(1);
  const before = p.slice(0, start).trim(), after = p.slice(q + 1).trim();
  const rest = [...paras.slice(0, i), ...(before ? [before] : []), ...(after ? [after] : []), ...paras.slice(i + 1)];
  return {question, rest};
}

// What a question's yes is called: its own verb where it opens with one
// ("Archive alpha?" is Archive), else Yes. A question that asks rather
// than proposes (Is, Use the, Should) is a Yes.
const ASK_NOT_VERBS = new Set(["is", "are", "do", "does", "did", "should", "will", "would", "can", "could",
                               "may", "has", "have", "was", "were", "this", "that", "the", "a", "an", "your"]);
function askYesWord(text){
  const first = askQuestion(String(text || "").split(/\n\s*\n/).map(p => p.trim()).filter(Boolean)).question;
  const w = (first.match(/^([A-Z][a-z]+)\b/) || [])[1] || "";
  return first.endsWith("?") && w && !ASK_NOT_VERBS.has(w.toLowerCase()) ? w : "Yes";
}

// The verbs that cannot be taken back, which wear .danger and come after
// Cancel (a-dialog: anything destructive last).
const ASK_DANGER = new Set(["Delete", "Remove", "Uninstall", "Discard", "Retire", "Reset", "Forget",
                            "Purge", "Wipe", "Unenroll", "Kill", "Drop", "Clear", "Revoke",
                            "Overwrite", "Replace", "Rotate", "Destroy", "Erase", "Unlink", "Abandon",
                            // ...and what loses work typed: a forced stop, leaving or
                            // closing over unsaved changes.
                            "Force", "Leave"]);
// ...and the ones that interrupt and lose nothing, which wear .caution, in
// amber (red is for what is dangerous; a restart is
// not): what they stop starts again.
const ASK_CAUTION = new Set(["Restart", "Reboot", "End", "Stop", "Shut", "Disconnect", "Lock", "Take", "Sign"]);

// confirm()'s replacement: true for its yes, false for Cancel. `verb` names
// the yes (askYesWord by default), `danger` marks it destructive, as a verb in
// ASK_DANGER is by itself.
async function askYes(text, {verb = "", danger = false, caution = false, title = "", parts = []} = {}){
  const v = verb || askYesWord(title || text), first = v.split(" ")[0];
  const red = danger || ASK_DANGER.has(v);
  return (await ask({title, text, parts, choices: [{label: v, value: true, danger: red,
                                                    caution: !red && (caution || ASK_CAUTION.has(first))}]})) === true;
}

// prompt()'s replacement: the text typed, or null for Cancel.
async function askText(text, {value = "", verb = "OK", label = ""} = {}){
  const got = await ask({text, choices: [{label: verb, value: true}], field: {value, label}});
  return got ? got.text : null;
}

// A yes that has to be typed, for what cannot be taken back: true when the
// word typed is `word`, false for Cancel, and false with `refused` said
// when it is another. The rest is handed to askText as it is.
async function askTyped(text, word, {verb, label, title, refused} = {}){
  const typed = await askText(text, {verb, label, title});
  if (typed == null) return false;
  if (String(typed).trim() === word) return true;
  notify(refused, true);
  return false;
}
