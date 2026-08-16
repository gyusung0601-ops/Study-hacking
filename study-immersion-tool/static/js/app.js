(() => {
  "use strict";

  const todayStr = () => {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  };

  const DATE = todayStr();

  document.getElementById("today-label").textContent = new Date().toLocaleDateString("ko-KR", {
    year: "numeric", month: "long", day: "numeric", weekday: "long",
  });

  // ------------------------------------------------------------- helpers --
  const api = {
    async get(url) {
      const res = await fetch(url);
      return res.json();
    },
    async send(url, method, body) {
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (res.status === 204) return null;
      return res.json();
    },
  };

  function debounce(fn, delay) {
    let t = null;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), delay);
    };
  }

  // ================================================================
  // 뽀모도로 타이머
  // ================================================================
  const timerDisplay = document.getElementById("timer-display");
  const modeBadge = document.getElementById("mode-badge");
  const btnStart = document.getElementById("btn-start");
  const btnPause = document.getElementById("btn-pause");
  const btnReset = document.getElementById("btn-reset");
  const inputFocus = document.getElementById("input-focus");
  const inputBreak = document.getElementById("input-break");
  const inputLongBreak = document.getElementById("input-long-break");
  const sessionCountEl = document.getElementById("session-count");
  const sessionMinutesEl = document.getElementById("session-minutes");

  const SETTINGS_KEY = "immersion.timer.settings";
  const savedSettings = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
  inputFocus.value = savedSettings.focus || 25;
  inputBreak.value = savedSettings.shortBreak || 5;
  inputLongBreak.value = savedSettings.longBreak || 15;

  function saveSettings() {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      focus: Number(inputFocus.value) || 25,
      shortBreak: Number(inputBreak.value) || 5,
      longBreak: Number(inputLongBreak.value) || 15,
    }));
  }
  [inputFocus, inputBreak, inputLongBreak].forEach((el) => el.addEventListener("change", saveSettings));

  const timer = {
    mode: "focus",           // 'focus' | 'break'
    remaining: Number(inputFocus.value) * 60,
    running: false,
    intervalId: null,
    completedFocusSessions: 0,
  };

  function formatTime(totalSeconds) {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  function renderTimer() {
    timerDisplay.textContent = formatTime(timer.remaining);
    modeBadge.textContent = timer.mode === "focus" ? "집중" : "휴식";
    modeBadge.classList.toggle("break", timer.mode === "break");
  }

  function tick() {
    timer.remaining -= 1;
    if (timer.remaining <= 0) {
      completeCurrentPhase();
      return;
    }
    renderTimer();
  }

  async function completeCurrentPhase() {
    playBeep();
    const finishedMode = timer.mode;
    const durationMinutes = finishedMode === "focus"
      ? Number(inputFocus.value)
      : (timer.completedFocusSessions % 4 === 0 ? Number(inputLongBreak.value) : Number(inputBreak.value));

    try {
      const summary = await api.send("/api/sessions", "POST", {
        date: DATE, type: finishedMode, duration_minutes: durationMinutes,
      });
      if (finishedMode === "focus") updateSessionInfo(summary);
    } catch (e) { /* offline-friendly: ignore network errors */ }

    if (finishedMode === "focus") {
      timer.completedFocusSessions += 1;
      const isLong = timer.completedFocusSessions % 4 === 0;
      timer.mode = "break";
      timer.remaining = (isLong ? Number(inputLongBreak.value) : Number(inputBreak.value)) * 60;
    } else {
      timer.mode = "focus";
      timer.remaining = Number(inputFocus.value) * 60;
    }
    renderTimer();
    notify(finishedMode === "focus" ? "집중 시간 종료! 휴식하세요." : "휴식 종료! 다시 집중해볼까요?");
  }

  function startTimer() {
    if (timer.running) return;
    timer.running = true;
    btnStart.disabled = true;
    btnPause.disabled = false;
    timer.intervalId = setInterval(tick, 1000);
  }

  function pauseTimer() {
    timer.running = false;
    btnStart.disabled = false;
    btnPause.disabled = true;
    clearInterval(timer.intervalId);
  }

  function resetTimer() {
    pauseTimer();
    timer.mode = "focus";
    timer.remaining = Number(inputFocus.value) * 60;
    renderTimer();
  }

  btnStart.addEventListener("click", startTimer);
  btnPause.addEventListener("click", pauseTimer);
  btnReset.addEventListener("click", resetTimer);
  [inputFocus, inputBreak, inputLongBreak].forEach((el) => el.addEventListener("change", () => {
    if (!timer.running) resetTimer();
  }));

  function notify(message) {
    if (window.Notification && Notification.permission === "granted") {
      new Notification("몰입", { body: message });
    }
    document.title = `${message} · 몰입`;
    setTimeout(() => { document.title = "몰입 - 나만의 공부 툴"; }, 4000);
  }
  if (window.Notification && Notification.permission === "default") {
    document.addEventListener("click", () => Notification.requestPermission(), { once: true });
  }

  function updateSessionInfo(summary) {
    sessionCountEl.textContent = summary.focus_count;
    sessionMinutesEl.textContent = Math.round(summary.focus_minutes);
  }

  renderTimer();
  api.get(`/api/summary?date=${DATE}`).then(updateSessionInfo).catch(() => {});

  // ================================================================
  // 알림음 (Web Audio beep)
  // ================================================================
  let audioCtx = null;
  function ensureAudioCtx() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    return audioCtx;
  }

  function playBeep() {
    const ctx = ensureAudioCtx();
    const now = ctx.currentTime;
    [0, 0.22].forEach((offset) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0, now + offset);
      gain.gain.linearRampToValueAtTime(0.25, now + offset + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, now + offset + 0.2);
      osc.connect(gain).connect(ctx.destination);
      osc.start(now + offset);
      osc.stop(now + offset + 0.22);
    });
  }

  // ================================================================
  // 집중 사운드 (화이트/핑크/브라운 노이즈, 전부 브라우저에서 생성)
  // ================================================================
  const soundButtons = document.querySelectorAll(".sound-btn");
  const volumeSlider = document.getElementById("volume");
  let noiseSource = null;
  let noiseGain = null;

  function makeNoiseBuffer(kind) {
    const ctx = ensureAudioCtx();
    const bufferSize = ctx.sampleRate * 4;
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const data = buffer.getChannelData(0);

    if (kind === "white") {
      for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;
    } else if (kind === "pink") {
      let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
      for (let i = 0; i < bufferSize; i++) {
        const white = Math.random() * 2 - 1;
        b0 = 0.99886 * b0 + white * 0.0555179;
        b1 = 0.99332 * b1 + white * 0.0750759;
        b2 = 0.96900 * b2 + white * 0.1538520;
        b3 = 0.86650 * b3 + white * 0.3104856;
        b4 = 0.55000 * b4 + white * 0.5329522;
        b5 = -0.7616 * b5 - white * 0.0168980;
        const pink = b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362;
        b6 = white * 0.115926;
        data[i] = pink * 0.11;
      }
    } else if (kind === "brown") {
      let last = 0;
      for (let i = 0; i < bufferSize; i++) {
        const white = Math.random() * 2 - 1;
        last = (last + 0.02 * white) / 1.02;
        data[i] = last * 3.5;
      }
    }
    return buffer;
  }

  function stopNoise() {
    if (noiseSource) {
      noiseSource.stop();
      noiseSource.disconnect();
      noiseSource = null;
    }
    if (noiseGain) {
      noiseGain.disconnect();
      noiseGain = null;
    }
  }

  function playNoise(kind) {
    stopNoise();
    if (kind === "none") return;
    const ctx = ensureAudioCtx();
    if (ctx.state === "suspended") ctx.resume();
    const buffer = makeNoiseBuffer(kind);
    noiseSource = ctx.createBufferSource();
    noiseSource.buffer = buffer;
    noiseSource.loop = true;
    noiseGain = ctx.createGain();
    noiseGain.gain.value = Number(volumeSlider.value) / 100;
    noiseSource.connect(noiseGain).connect(ctx.destination);
    noiseSource.start();
  }

  soundButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      soundButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      playNoise(btn.dataset.sound);
    });
  });

  volumeSlider.addEventListener("input", () => {
    if (noiseGain) noiseGain.gain.value = Number(volumeSlider.value) / 100;
  });

  // ================================================================
  // 오늘의 목표 / 연습장 / 피드백 (자동 저장)
  // ================================================================
  const goalEl = document.getElementById("goal");
  const notepadEl = document.getElementById("notepad");
  const feedbackEl = document.getElementById("feedback");

  api.get(`/api/note?date=${DATE}`).then((note) => {
    goalEl.value = note.goal || "";
    notepadEl.value = note.notepad || "";
    feedbackEl.value = note.feedback || "";
  }).catch(() => {});

  const saveNote = debounce((field, value) => {
    api.send("/api/note", "PUT", { date: DATE, [field]: value }).catch(() => {});
  }, 600);

  goalEl.addEventListener("input", () => saveNote("goal", goalEl.value));
  notepadEl.addEventListener("input", () => saveNote("notepad", notepadEl.value));
  feedbackEl.addEventListener("input", () => saveNote("feedback", feedbackEl.value));

  // ================================================================
  // 할 일 (할당량) 체크리스트
  // ================================================================
  const todoForm = document.getElementById("todo-form");
  const todoInput = document.getElementById("todo-input");
  const todoList = document.getElementById("todo-list");
  const todoProgress = document.getElementById("todo-progress");

  function renderTodoProgress(tasks) {
    if (!tasks.length) {
      todoProgress.textContent = "오늘 등록된 할 일이 없습니다.";
      return;
    }
    const done = tasks.filter((t) => t.done).length;
    todoProgress.textContent = `${done} / ${tasks.length} 완료`;
  }

  function renderTodoItem(task) {
    const li = document.createElement("li");
    li.className = "todo-item" + (task.done ? " done" : "");
    li.dataset.id = task.id;

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = !!task.done;
    checkbox.addEventListener("change", async () => {
      const updated = await api.send(`/api/tasks/${task.id}`, "PATCH", { done: checkbox.checked });
      li.classList.toggle("done", !!updated.done);
      refreshProgress();
    });

    const span = document.createElement("span");
    span.textContent = task.text;

    const delBtn = document.createElement("button");
    delBtn.textContent = "✕";
    delBtn.title = "삭제";
    delBtn.addEventListener("click", async () => {
      await api.send(`/api/tasks/${task.id}`, "DELETE");
      li.remove();
      refreshProgress();
    });

    li.append(checkbox, span, delBtn);
    return li;
  }

  function refreshProgress() {
    const tasks = [...todoList.querySelectorAll(".todo-item")].map((li) => ({
      done: li.classList.contains("done"),
    }));
    renderTodoProgress(tasks);
  }

  api.get(`/api/tasks?date=${DATE}`).then((tasks) => {
    todoList.innerHTML = "";
    tasks.forEach((t) => todoList.appendChild(renderTodoItem(t)));
    renderTodoProgress(tasks);
  }).catch(() => {});

  todoForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = todoInput.value.trim();
    if (!text) return;
    const task = await api.send("/api/tasks", "POST", { date: DATE, text });
    todoList.appendChild(renderTodoItem(task));
    todoInput.value = "";
    refreshProgress();
  });

  // ================================================================
  // 통계 차트 (최근 7일)
  // ================================================================
  const canvas = document.getElementById("stats-chart");
  const ctx2d = canvas.getContext("2d");

  function drawChart(data) {
    const dpr = window.devicePixelRatio || 1;
    const cssWidth = canvas.clientWidth || 600;
    const cssHeight = 220;
    canvas.width = cssWidth * dpr;
    canvas.height = cssHeight * dpr;
    ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx2d.clearRect(0, 0, cssWidth, cssHeight);

    const padding = { top: 16, right: 12, bottom: 28, left: 36 };
    const chartW = cssWidth - padding.left - padding.right;
    const chartH = cssHeight - padding.top - padding.bottom;
    const maxMinutes = Math.max(60, ...data.map((d) => d.minutes));

    ctx2d.strokeStyle = "#262b36";
    ctx2d.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartH / 4) * i;
      ctx2d.beginPath();
      ctx2d.moveTo(padding.left, y);
      ctx2d.lineTo(cssWidth - padding.right, y);
      ctx2d.stroke();
    }

    const barSlot = chartW / data.length;
    const barWidth = barSlot * 0.5;

    data.forEach((d, i) => {
      const barHeight = (d.minutes / maxMinutes) * chartH;
      const x = padding.left + i * barSlot + (barSlot - barWidth) / 2;
      const y = padding.top + chartH - barHeight;

      ctx2d.fillStyle = "#6f9dff";
      ctx2d.beginPath();
      ctx2d.roundRect(x, y, barWidth, barHeight, 4);
      ctx2d.fill();

      ctx2d.fillStyle = "#8b91a3";
      ctx2d.font = "11px sans-serif";
      ctx2d.textAlign = "center";
      const label = d.date.slice(5).replace("-", "/");
      ctx2d.fillText(label, x + barWidth / 2, padding.top + chartH + 16);

      if (d.minutes > 0) {
        ctx2d.fillStyle = "#e8eaf0";
        ctx2d.fillText(Math.round(d.minutes), x + barWidth / 2, y - 6);
      }
    });
  }

  api.get("/api/stats?days=7").then(drawChart).catch(() => {});
  window.addEventListener("resize", debounce(() => {
    api.get("/api/stats?days=7").then(drawChart).catch(() => {});
  }, 300));
})();
