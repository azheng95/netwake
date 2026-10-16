const state = {
  devices: [],
  activity: [],
  config: null,
  interfaces: [],
  token: localStorage.getItem("netwake-token") || "",
};

const $ = (id) => document.getElementById(id);
const tokenInput = $("tokenInput");
tokenInput.value = state.token;

function headers() {
  return state.token ? { "X-Admin-Token": state.token } : {};
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...headers(), ...(options.headers || {}) },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function showToast(message, error = false) {
  const toast = $("toast");
  toast.textContent = message;
  toast.style.background = error ? "var(--red)" : "#1e2732";
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 3000);
}

function formatTime(value) {
  if (!value) return "未记录";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[char]));
}

function renderStats() {
  $("totalCount").textContent = state.devices.length;
  $("onlineCount").textContent = state.devices.filter((device) => device.is_online).length;
  $("wolCount").textContent = state.devices.filter((device) => device.wol_status === "verified").length;
  const scan = state.activity.find((item) => item.kind === "scan");
  $("lastScan").textContent = scan ? formatTime(scan.created_at).slice(5, 16) : "未执行";
}

function renderDevices() {
  const filter = $("filterSelect").value;
  const devices = state.devices.filter((device) => {
    if (filter === "online") return device.is_online;
    if (filter === "wol") return device.wol_status === "verified";
    return true;
  });
  if (!devices.length) {
    $("deviceList").innerHTML = '<div class="empty">暂无设备。先扫描局域网，或手动添加一台设备。</div>';
    return;
  }
  $("deviceList").innerHTML = devices.map((device) => `
    <div class="device-row">
      <div>
        <div class="device-name">${escapeHtml(device.name || device.mac)}</div>
        <div class="device-meta">${escapeHtml(device.hostname || "未解析主机名")} · ${escapeHtml(device.mac)}</div>
      </div>
      <div class="device-address">
        <div>${escapeHtml(device.ip || "无 IP")}</div>
        <div class="device-meta">${device.last_seen_at ? `最近在线 ${escapeHtml(formatTime(device.last_seen_at))}` : "尚未探测"}</div>
      </div>
      <div class="device-status">
        <span class="pill ${device.is_online ? "online" : ""}">${device.is_online ? "在线" : device.last_seen_at ? "离线" : "未探测"}</span>
        <span class="pill ${device.wol_status === "verified" ? "verified" : ""}">${device.wol_status === "verified" ? "WoL 已验证" : device.wol_status === "unsupported" ? "WoL 不支持" : "WoL 未验证"}</span>
      </div>
      <div class="row-actions">
        <button class="mini-button wake" data-action="wake" data-id="${device.id}">唤醒</button>
        <button class="mini-button" data-action="probe" data-id="${device.id}" title="探测在线状态" aria-label="探测在线状态">探测</button>
        <button class="mini-button" data-action="edit" data-id="${device.id}" title="编辑设备" aria-label="编辑设备">编辑</button>
        <button class="mini-button danger" data-action="delete" data-id="${device.id}" title="删除设备" aria-label="删除设备">删除</button>
      </div>
    </div>
  `).join("");
}

function renderActivity() {
  if (!state.activity.length) {
    $("activityList").innerHTML = '<div class="empty">还没有活动记录。</div>';
    return;
  }
  $("activityList").innerHTML = state.activity.map((item) => `
    <div class="activity-item">
      <strong>${escapeHtml(item.message)}</strong>
      <small>${escapeHtml(formatTime(item.created_at))}</small>
    </div>
  `).join("");
}

async function loadAll() {
  try {
    state.config = await api("/api/config");
    $("tokenField").style.display = state.config.auth_enabled ? "grid" : "none";
    if (state.config.auth_enabled && !state.token) {
      $("agentDot").className = "status-dot";
      $("agentName").textContent = "需要管理令牌";
      $("agentMeta").textContent = "请在右上角输入令牌";
      throw new Error("请输入管理令牌");
    }
    $("agentName").textContent = "管理端已连接";
    const [devices, activity] = await Promise.all([api("/api/devices"), api("/api/activity")]);
    state.devices = devices;
    state.activity = activity;
    renderStats(); renderDevices(); renderActivity();
    await loadInterfaces();
    $("toast").classList.remove("show");
    await loadAgentStatus();
  } catch (error) {
    $("agentMeta").textContent = error.message;
    showToast(error.message, true);
  }
}

async function loadInterfaces() {
  const select = $("interfaceInput");
  try {
    const result = await api("/api/discovery/interfaces");
    state.interfaces = (result.interfaces || []).filter((item) => item.cidr);
    if (!state.interfaces.length) {
      select.innerHTML = '<option value="">未找到可扫描的局域网</option>';
      return;
    }
    const selected = select.value;
    select.innerHTML = state.interfaces.map((item) =>
      `<option value="${escapeHtml(item.name)}" data-cidr="${escapeHtml(item.cidr)}">${escapeHtml(item.name)} · ${escapeHtml(item.ipv4)}（${escapeHtml(item.cidr)}）</option>`
    ).join("");
    if (state.interfaces.some((item) => item.name === selected)) select.value = selected;
    else if (state.config?.default_interface && state.interfaces.some((item) => item.name === state.config.default_interface)) {
      select.value = state.config.default_interface;
    }
  } catch (error) {
    select.innerHTML = '<option value="">无法获取网卡信息</option>';
    $("agentMeta").textContent = error.message;
  }
}

async function showInitialTokenSetup() {
  try {
    const result = await api("/api/setup/initial-token");
    $("initialTokenValue").value = result.token;
    state.token = result.token;
    tokenInput.value = result.token;
    $("initialTokenDialog").showModal();
  } catch (error) {
    if (!error.message.includes("Initial token setup is complete")) {
      showToast(error.message, true);
    }
  }
}

async function copyInitialToken() {
  const tokenField = $("initialTokenValue");
  tokenField.focus();
  tokenField.select();
  try {
    await navigator.clipboard.writeText(tokenField.value);
    showToast("管理令牌已复制，请妥善保存");
  } catch {
    showToast("已选中令牌，请按 Ctrl+C 复制");
  }
}

async function confirmInitialTokenSaved() {
  try {
    await api("/api/setup/token-saved", { method: "POST" });
    localStorage.setItem("netwake-token", state.token);
    $("initialTokenDialog").close();
    await loadAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function loadAgentStatus() {
  try {
    const agent = await api("/api/agent/status");
    $("agentDot").className = "status-dot ok";
    $("agentName").textContent = agent.name || "Linux Agent";
    $("agentMeta").textContent = `Agent ${agent.version || ""} · ${agent.interface || "默认网卡"}`;
  } catch (error) {
    $("agentDot").className = "status-dot error";
    $("agentName").textContent = "Agent 不可用";
    $("agentMeta").textContent = error.message;
  }
}

async function scan() {
  const button = $("scanButton");
  const option = $("interfaceInput").selectedOptions[0];
  if (!option?.dataset.cidr) {
    showToast("未找到可扫描的局域网，请检查 Agent 网卡配置", true);
    return;
  }
  button.disabled = true; button.textContent = "扫描中…";
  try {
    const result = await api("/api/discovery/scan", {
      method: "POST",
    body: JSON.stringify({
      cidr: option.dataset.cidr,
      interface: $("interfaceInput").value || null,
    }),
    });
    showToast(`扫描完成，发现 ${result.devices.length} 台在线设备`);
    await loadAll();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false; button.textContent = "扫描设备";
  }
}

function openDialog(device = null) {
  $("deviceForm").reset();
  $("deviceId").value = device?.id || "";
  $("dialogTitle").textContent = device ? "编辑设备" : "添加设备";
  $("nameInput").value = device?.name || "";
  $("macInput").value = device?.mac || "";
  $("ipInput").value = device?.ip || "";
  $("broadcastInput").value = device?.broadcast || "";
  $("wolStatusInput").value = device?.wol_status || "unknown";
  $("notesInput").value = device?.notes || "";
  $("advancedFields").open = Boolean(device);
  $("macInput").disabled = Boolean(device);
  $("deviceDialog").showModal();
}

async function saveDevice(event) {
  event.preventDefault();
  const id = $("deviceId").value;
  const payload = {
    name: $("nameInput").value,
    mac: $("macInput").value,
  };
  if (id || $("advancedFields").open) {
    Object.assign(payload, {
      ip: $("ipInput").value || null,
      broadcast: $("broadcastInput").value || null,
      wol_status: $("wolStatusInput").value,
      notes: $("notesInput").value,
    });
  }
  try {
    const updatePayload = { ...payload };
    delete updatePayload.mac;
    await api(id ? `/api/devices/${id}` : "/api/devices", {
      method: id ? "PATCH" : "POST",
      body: JSON.stringify(id ? updatePayload : payload),
    });
    $("deviceDialog").close();
    showToast("设备已保存");
    await loadAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function handleDeviceAction(event) {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const device = state.devices.find((item) => String(item.id) === button.dataset.id);
  if (!device) return;
  try {
    if (button.dataset.action === "wake") {
      const response = await api(`/api/devices/${device.id}/wake`, { method: "POST" });
      showToast(response.result.packet_sent
        ? `已发送 WoL 包至 ${device.name || device.mac}，尚未确认设备开机`
        : "Magic Packet 未能完整发送", !response.result.packet_sent);
      await loadAll();
    } else if (button.dataset.action === "probe") {
      const result = await api(`/api/devices/${device.id}/probe`, { method: "POST" });
      showToast(result.online ? "设备在线" : "暂未检测到设备");
      await loadAll();
    } else if (button.dataset.action === "edit") {
      openDialog(device);
    } else if (button.dataset.action === "delete" && confirm(`确定删除 ${device.name || device.mac}？`)) {
      await api(`/api/devices/${device.id}`, { method: "DELETE" });
      showToast("设备已删除");
      await loadAll();
    }
  } catch (error) {
    showToast(error.message, true);
  }
}

tokenInput.addEventListener("input", () => {
  state.token = tokenInput.value.trim();
});
async function connectWithToken() {
  state.token = tokenInput.value.trim();
  localStorage.setItem("netwake-token", state.token);
  window.clearTimeout(tokenInput.refreshTimer);
  await loadAll();
}
$("tokenButton").addEventListener("click", connectWithToken);
tokenInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") connectWithToken();
});
$("refreshButton").addEventListener("click", loadAll);
$("copyInitialTokenButton").addEventListener("click", copyInitialToken);
$("confirmTokenSavedButton").addEventListener("click", confirmInitialTokenSaved);
$("tokenHelpButton").addEventListener("click", () => $("tokenHelpDialog").showModal());
$("closeTokenHelpButton").addEventListener("click", () => $("tokenHelpDialog").close());
$("scanButton").addEventListener("click", scan);
$("addButton").addEventListener("click", () => openDialog());
$("filterSelect").addEventListener("change", renderDevices);
$("deviceList").addEventListener("click", handleDeviceAction);
$("deviceForm").addEventListener("submit", saveDevice);
$("deviceDialog").querySelectorAll("[data-close-dialog]").forEach((button) => {
  button.addEventListener("click", () => $("deviceDialog").close());
});

showInitialTokenSetup().then(loadAll);
