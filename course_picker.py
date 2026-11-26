"""Searchable course dropdown whose options wrap onto two lines (course, then tag chips).
st.selectbox can't do that: its option rows have a fixed height."""
import streamlit as st

_HTML = """
<div class="cp">
  <div class="field">
    <input type="text" role="combobox" aria-expanded="false" aria-autocomplete="list" autocomplete="off" />
    <button type="button" class="clear" aria-label="Clear" hidden>✕</button>
  </div>
  <ul role="listbox" hidden></ul>
</div>
"""

_CSS = """
.cp { font-family: var(--st-font); font-size: var(--st-base-font-size); color: var(--st-text-color); }
.field { position: relative; }
input {
  box-sizing: border-box; width: 100%; height: 2.5rem; padding: 0 2rem 0 0.75rem;
  font: inherit; color: inherit; background: var(--st-secondary-background-color);
  border: 1px solid var(--st-widget-border-color, transparent); border-radius: var(--st-base-radius);
}
input:focus { outline: none; border-color: var(--st-primary-color); }
.clear {
  position: absolute; right: 0.25rem; top: 50%; transform: translateY(-50%);
  border: 0; background: none; color: var(--st-gray-text-color); cursor: pointer; font: inherit;
}
ul {
  list-style: none; margin: 0.25rem 0 0; padding: 0.25rem 0; max-height: 20rem; overflow-y: auto;
  background: var(--st-background-color); border: 1px solid var(--st-border-color);
  border-radius: var(--st-base-radius);
}
li { padding: 0.4rem 0.75rem; cursor: pointer; line-height: 1.35; }
li.active { background: var(--st-secondary-background-color); }
li.empty { cursor: default; color: var(--st-gray-text-color); }
.tags { display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 0.2rem; }
.tag { font-size: 0.75rem; padding: 0 0.4rem; border-radius: 0.5rem;
       background: var(--st-gray-background-color); color: var(--st-gray-text-color); }
.tag.taken { background: var(--st-green-background-color); color: var(--st-green-text-color); }
.tag.double { background: var(--st-violet-background-color); color: var(--st-violet-text-color); }
.tag.popular { background: var(--st-yellow-background-color); color: var(--st-yellow-text-color); }
"""

_JS = """
const STATE = new WeakMap()

export default function ({ data, parentElement, setStateValue }) {
  const input = parentElement.querySelector("input")
  const list = parentElement.querySelector("ul")
  const clear = parentElement.querySelector(".clear")
  const opts = data.options
  const label = code => { const o = opts.find(o => o.code === code); return o ? `${o.code} — ${o.title}` : "" }

  let s = STATE.get(parentElement)
  if (!s) { s = { open: false, active: 0, shown: [] }; STATE.set(parentElement, s) }
  s.value = data.value ?? null
  input.placeholder = data.placeholder
  if (document.activeElement !== input && parentElement.activeElement !== input) input.value = label(s.value)
  clear.hidden = !s.value

  const render = () => {
    const q = input.value.trim().toLowerCase()
    // Typing filters; an untouched field showing the current pick lists everything.
    const filter = q && input.value !== label(s.value)
    s.shown = filter ? opts.filter(o => `${o.code} ${o.title}`.toLowerCase().includes(q)) : opts
    s.active = Math.min(s.active, Math.max(s.shown.length - 1, 0))
    list.replaceChildren(...s.shown.map((o, i) => {
      const li = document.createElement("li")
      li.setAttribute("role", "option")
      li.setAttribute("aria-selected", String(o.code === s.value))
      if (i === s.active) li.className = "active"
      const main = document.createElement("div")
      main.textContent = `${o.code} — ${o.title}`
      li.append(main)
      if (o.tags.length) {
        const tags = document.createElement("div")
        tags.className = "tags"
        for (const [kind, text] of o.tags) {
          const t = document.createElement("span")
          t.className = `tag ${kind}`
          t.textContent = text
          tags.append(t)
        }
        li.append(tags)
      }
      li.onpointerdown = e => { e.preventDefault(); choose(o.code) }  // before blur closes the list
      li.onpointermove = () => { if (s.active !== i) { s.active = i; render() } }
      return li
    }))
    if (!s.shown.length) {
      const li = document.createElement("li")
      li.className = "empty"
      li.textContent = "No matching courses"
      list.append(li)
    }
    list.hidden = !s.open
    input.setAttribute("aria-expanded", String(s.open))
    list.querySelector("li.active")?.scrollIntoView({ block: "nearest" })
  }
  const open = () => { if (!s.open) { s.open = true; render() } }
  const close = () => { s.open = false; input.value = label(s.value); render() }
  const choose = code => {
    s.value = code; clear.hidden = !code; setStateValue("value", code); close(); input.blur()
  }

  input.onfocus = () => { input.select(); open() }
  input.onclick = open
  input.oninput = () => { s.open = true; s.active = 0; render() }
  input.onblur = close
  input.onkeydown = e => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault()
      if (!s.open) return open()
      const n = s.shown.length
      if (n) { s.active = (s.active + (e.key === "ArrowDown" ? 1 : n - 1)) % n; render() }
    } else if (e.key === "Enter" && s.open && s.shown[s.active]) {
      e.preventDefault(); choose(s.shown[s.active].code)
    } else if (e.key === "Escape") {
      close(); input.blur()
    }
  }
  clear.onclick = () => { choose(null) }
  render()
}
"""

_PICKER = st.components.v2.component("course_picker", html=_HTML, css=_CSS, js=_JS)


def course_picker(options, *, key, placeholder="Add a course…"):
    """options: [{"code", "title", "tags": [(kind, text), ...]}]. Returns the picked code or None."""
    value = st.session_state.get(key, {}).get("value")
    if value not in {o["code"] for o in options}:
        value = None
    _PICKER(key=key, data={"options": options, "value": value, "placeholder": placeholder},
            default={"value": None}, on_value_change=lambda: None)
    return value
