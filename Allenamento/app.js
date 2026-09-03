const STORAGE_KEY = "allenamento-app-v1";
const dayNames = ["A", "B", "C", "D"];

const defaultState = {
  activeDay: 0,
  plans: [
    {
      name: "Forza",
      exercises: [
        { id: crypto.randomUUID(), name: "Pressa", sets: 4, reps: "10", notes: "Carico controllato, schiena aderente.", done: [] },
        { id: crypto.randomUUID(), name: "Chest press", sets: 3, reps: "10", notes: "Spinta fluida, pausa breve in chiusura.", done: [] },
        { id: crypto.randomUUID(), name: "Lat machine", sets: 3, reps: "12", notes: "Scapole basse, niente slancio.", done: [] },
        { id: crypto.randomUUID(), name: "Plank", sets: 3, reps: "40 sec", notes: "Addome compatto, respirazione regolare.", done: [] }
      ]
    },
    {
      name: "Cardio",
      exercises: [
        { id: crypto.randomUUID(), name: "Camminata inclinata", sets: 1, reps: "20 min", notes: "Ritmo sostenibile, senza affanno.", done: [] },
        { id: crypto.randomUUID(), name: "Bike", sets: 4, reps: "3 min", notes: "Recupero 90 sec tra i blocchi.", done: [] },
        { id: crypto.randomUUID(), name: "Stretching gambe", sets: 3, reps: "30 sec", notes: "Movimento lento, senza rimbalzi.", done: [] }
      ]
    },
    {
      name: "Mobilità",
      exercises: [
        { id: crypto.randomUUID(), name: "Spalle con elastico", sets: 3, reps: "15", notes: "Tenere le costole basse.", done: [] },
        { id: crypto.randomUUID(), name: "Cat cow", sets: 2, reps: "12", notes: "Muovere una vertebra alla volta.", done: [] },
        { id: crypto.randomUUID(), name: "Squat a corpo libero", sets: 3, reps: "12", notes: "Scendere comodo, ginocchia stabili.", done: [] }
      ]
    },
    {
      name: "Richiamo",
      exercises: [
        { id: crypto.randomUUID(), name: "Rematore", sets: 3, reps: "10", notes: "Gomiti vicini, busto fermo.", done: [] },
        { id: crypto.randomUUID(), name: "Affondi", sets: 3, reps: "8+8", notes: "Passo lungo e controllo.", done: [] },
        { id: crypto.randomUUID(), name: "Curl manubri", sets: 3, reps: "12", notes: "Polsi neutri.", done: [] },
        { id: crypto.randomUUID(), name: "Respirazione", sets: 1, reps: "3 min", notes: "Defaticamento.", done: [] }
      ]
    }
  ],
  history: []
};

let state = loadState();
let timerSeconds = 90;
let timerRemaining = 90;
let timerHandle = null;

const todayLabel = document.querySelector("#todayLabel");
const dayTabs = document.querySelector("#dayTabs");
const activeDayName = document.querySelector("#activeDayName");
const exerciseList = document.querySelector("#exerciseList");
const progressCircle = document.querySelector("#progressCircle");
const progressText = document.querySelector("#progressText");
const timerFace = document.querySelector("#timerFace");
const timerStartBtn = document.querySelector("#timerStartBtn");
const timerResetBtn = document.querySelector("#timerResetBtn");
const exerciseForm = document.querySelector("#exerciseForm");
const weekSessions = document.querySelector("#weekSessions");
const weekSets = document.querySelector("#weekSets");
const bestStreak = document.querySelector("#bestStreak");
const historyText = document.querySelector("#historyText");

function loadState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (saved && Array.isArray(saved.plans)) return saved;
  } catch (_error) {}
  return structuredClone(defaultState);
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function formatToday() {
  const formatter = new Intl.DateTimeFormat("it-IT", { weekday: "long", day: "2-digit", month: "long" });
  const text = formatter.format(new Date());
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function formatTimer(seconds) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const rest = Math.max(0, seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${rest}`;
}

function currentPlan() {
  return state.plans[state.activeDay];
}

function completedSets(plan = currentPlan()) {
  return plan.exercises.reduce((sum, exercise) => sum + exercise.done.filter(Boolean).length, 0);
}

function totalSets(plan = currentPlan()) {
  return plan.exercises.reduce((sum, exercise) => sum + Number(exercise.sets || 0), 0);
}

function renderTabs() {
  dayTabs.innerHTML = "";
  state.plans.forEach((plan, index) => {
    const button = document.createElement("button");
    button.className = index === state.activeDay ? "active" : "";
    button.type = "button";
    button.innerHTML = `${dayNames[index] || index + 1}<span>${plan.name}</span>`;
    button.addEventListener("click", () => {
      state.activeDay = index;
      saveState();
      render();
    });
    dayTabs.append(button);
  });
}

function renderExercises() {
  const plan = currentPlan();
  activeDayName.textContent = `${dayNames[state.activeDay]} · ${plan.name}`;
  exerciseList.innerHTML = "";

  plan.exercises.forEach((exercise) => {
    const complete = exercise.done.filter(Boolean).length >= exercise.sets;
    const card = document.createElement("article");
    card.className = `exercise-card${complete ? " done" : ""}`;

    const info = document.createElement("div");
    info.innerHTML = `
      <div class="exercise-title">
        <h3>${escapeHtml(exercise.name)}</h3>
        <span class="badge">${exercise.sets} × ${escapeHtml(exercise.reps)}</span>
      </div>
      <p class="exercise-notes">${escapeHtml(exercise.notes || "Nessuna nota")}</p>
    `;

    const buttons = document.createElement("div");
    buttons.className = "set-buttons";
    for (let i = 0; i < exercise.sets; i += 1) {
      const setButton = document.createElement("button");
      setButton.type = "button";
      setButton.className = exercise.done[i] ? "checked" : "";
      setButton.textContent = i + 1;
      setButton.title = `Serie ${i + 1}`;
      setButton.addEventListener("click", () => {
        exercise.done[i] = !exercise.done[i];
        saveState();
        render();
      });
      buttons.append(setButton);
    }

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "delete-exercise";
    deleteButton.textContent = "×";
    deleteButton.title = "Elimina esercizio";
    deleteButton.addEventListener("click", () => {
      plan.exercises = plan.exercises.filter((item) => item.id !== exercise.id);
      saveState();
      render();
    });
    buttons.append(deleteButton);

    card.append(info, buttons);
    exerciseList.append(card);
  });
}

function renderProgress() {
  const total = totalSets();
  const done = completedSets();
  const percent = total ? Math.round((done / total) * 100) : 0;
  progressText.textContent = `${percent}%`;
  progressCircle.style.strokeDashoffset = String(308 - (308 * percent) / 100);
}

function renderStats() {
  const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const recent = state.history.filter((session) => new Date(session.date).getTime() >= weekAgo);
  weekSessions.textContent = recent.length;
  weekSets.textContent = recent.reduce((sum, session) => sum + session.sets, 0);
  bestStreak.textContent = calculateStreak();

  if (!state.history.length) {
    historyText.textContent = "Nessuna sessione salvata.";
    return;
  }
  const last = state.history.slice(-3).reverse().map((session) => {
    const date = new Intl.DateTimeFormat("it-IT", { day: "2-digit", month: "2-digit" }).format(new Date(session.date));
    return `${date}: ${session.plan}, ${session.sets} serie`;
  });
  historyText.textContent = last.join(" · ");
}

function calculateStreak() {
  const days = [...new Set(state.history.map((session) => session.date.slice(0, 10)))].sort().reverse();
  if (!days.length) return 0;
  let streak = 0;
  let cursor = new Date();
  cursor.setHours(0, 0, 0, 0);
  for (const day of days) {
    const current = cursor.toISOString().slice(0, 10);
    if (day === current) {
      streak += 1;
      cursor.setDate(cursor.getDate() - 1);
    } else if (streak === 0) {
      cursor.setDate(cursor.getDate() - 1);
      if (day === cursor.toISOString().slice(0, 10)) {
        streak += 1;
        cursor.setDate(cursor.getDate() - 1);
      }
    } else {
      break;
    }
  }
  return streak;
}

function renderTimer() {
  timerFace.textContent = formatTimer(timerRemaining);
  timerStartBtn.textContent = timerHandle ? "Pausa" : "Avvia";
}

function render() {
  todayLabel.textContent = formatToday();
  renderTabs();
  renderExercises();
  renderProgress();
  renderStats();
  renderTimer();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;"
  }[char]));
}

document.querySelectorAll("[data-timer]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-timer]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    timerSeconds = Number(button.dataset.timer);
    timerRemaining = timerSeconds;
    clearInterval(timerHandle);
    timerHandle = null;
    renderTimer();
  });
});

timerStartBtn.addEventListener("click", () => {
  if (timerHandle) {
    clearInterval(timerHandle);
    timerHandle = null;
    renderTimer();
    return;
  }
  timerHandle = setInterval(() => {
    timerRemaining -= 1;
    if (timerRemaining <= 0) {
      clearInterval(timerHandle);
      timerHandle = null;
      timerRemaining = timerSeconds;
      if (navigator.vibrate) navigator.vibrate([180, 80, 180]);
    }
    renderTimer();
  }, 1000);
  renderTimer();
});

timerResetBtn.addEventListener("click", () => {
  clearInterval(timerHandle);
  timerHandle = null;
  timerRemaining = timerSeconds;
  renderTimer();
});

exerciseForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const exercise = {
    id: crypto.randomUUID(),
    name: document.querySelector("#exerciseName").value.trim(),
    sets: Number(document.querySelector("#exerciseSets").value),
    reps: document.querySelector("#exerciseReps").value.trim(),
    notes: document.querySelector("#exerciseNotes").value.trim(),
    done: []
  };
  currentPlan().exercises.push(exercise);
  exerciseForm.reset();
  document.querySelector("#exerciseSets").value = 3;
  saveState();
  render();
});

document.querySelector("#resetDayBtn").addEventListener("click", () => {
  currentPlan().exercises.forEach((exercise) => { exercise.done = []; });
  saveState();
  render();
});

document.querySelector("#finishSessionBtn").addEventListener("click", () => {
  const plan = currentPlan();
  const sets = completedSets(plan);
  state.history.push({ date: new Date().toISOString(), plan: `${dayNames[state.activeDay]} · ${plan.name}`, sets });
  plan.exercises.forEach((exercise) => { exercise.done = []; });
  saveState();
  render();
});

document.querySelector("#clearHistoryBtn").addEventListener("click", () => {
  state.history = [];
  saveState();
  render();
});

document.querySelector("#printBtn").addEventListener("click", () => window.print());

render();
