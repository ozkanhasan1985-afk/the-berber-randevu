const pinForm = document.querySelector("#pinForm");
const pinInput = document.querySelector("#pinInput");
const pinMessage = document.querySelector("#pinMessage");
const dashboardGrid = document.querySelector("#dashboardGrid");
const bookingRows = document.querySelector("#bookingRows");
const customerGrid = document.querySelector("#customerGrid");
const bookingSearch = document.querySelector("#bookingSearch");
const bookingDate = document.querySelector("#bookingDate");
const statusFilter = document.querySelector("#statusFilter");
const customerSearch = document.querySelector("#customerSearch");
const refreshBookings = document.querySelector("#refreshBookings");
const refreshCustomers = document.querySelector("#refreshCustomers");

const labels = {
  pending: "Bekliyor",
  confirmed: "Onaylandı",
  completed: "Tamamlandı",
  cancelled: "İptal",
  no_show: "Gelmedi",
};

let adminPin = localStorage.getItem("theBerberAdminPin") || "";

function todayIso() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function adminHeaders() {
  return { "Content-Type": "application/json", "X-Admin-Pin": adminPin };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: adminHeaders(),
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "İşlem tamamlanamadı.");
  return data;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderDashboard(summary) {
  const cards = [
    ["Bugün", summary.today],
    ["Bekleyen", summary.pending],
    ["Müşteri", summary.customers],
    ["Yaklaşan", summary.upcoming],
  ];
  dashboardGrid.innerHTML = cards
    .map(
      ([label, value]) => `
        <article class="dashboard-card">
          <strong>${value}</strong>
          <span>${label}</span>
        </article>
      `,
    )
    .join("");
}

function renderBookings(bookings) {
  if (bookings.length === 0) {
    bookingRows.innerHTML = `<tr><td colspan="7">Kayıt bulunamadı.</td></tr>`;
    return;
  }
  bookingRows.innerHTML = bookings
    .map(
      (booking) => `
        <tr>
          <td>${booking.id}</td>
          <td>
            <strong>${escapeHtml(booking.customer_name)}</strong><br>
            <small>${escapeHtml(booking.phone)}</small>
          </td>
          <td>${escapeHtml(booking.service_name)}</td>
          <td>${escapeHtml(booking.barber_name)}</td>
          <td>${booking.date} / ${booking.time}</td>
          <td><span class="status ${booking.status}">${labels[booking.status]}</span></td>
          <td>
            <div class="action-row">
              <button class="small-button" data-status="confirmed" data-id="${booking.id}" type="button">Onayla</button>
              <button class="small-button" data-status="completed" data-id="${booking.id}" type="button">Tamamla</button>
              <button class="small-button" data-status="cancelled" data-id="${booking.id}" type="button">İptal</button>
            </div>
          </td>
        </tr>
      `,
    )
    .join("");
}

function renderCustomers(customers) {
  if (customers.length === 0) {
    customerGrid.innerHTML = `<article class="customer-card"><p>Müşteri bulunamadı.</p></article>`;
    return;
  }
  customerGrid.innerHTML = customers
    .map(
      (customer) => `
        <article class="customer-card">
          <h3>${escapeHtml(customer.name)}</h3>
          <p>${escapeHtml(customer.phone)}<br>${escapeHtml(customer.email || "E-posta yok")}</p>
          <div class="customer-meta">
            <span>${customer.appointment_count} randevu</span>
            <span>${escapeHtml(customer.last_visit || "Henüz ziyaret yok")}</span>
          </div>
        </article>
      `,
    )
    .join("");
}

async function loadSummary() {
  renderDashboard(await api("/api/admin/summary"));
}

async function loadBookings() {
  const params = new URLSearchParams();
  if (bookingSearch.value.trim()) params.set("q", bookingSearch.value.trim());
  if (bookingDate.value) params.set("date", bookingDate.value);
  if (statusFilter.value) params.set("status", statusFilter.value);
  const data = await api(`/api/admin/bookings?${params.toString()}`);
  renderBookings(data.bookings);
}

async function loadCustomers() {
  const params = new URLSearchParams();
  if (customerSearch.value.trim()) params.set("q", customerSearch.value.trim());
  const data = await api(`/api/admin/customers?${params.toString()}`);
  renderCustomers(data.customers);
}

async function loadAll() {
  try {
    pinMessage.textContent = "Panel yükleniyor...";
    await loadSummary();
    await loadBookings();
    await loadCustomers();
    pinMessage.textContent = "Panel hazır.";
    pinMessage.classList.remove("error");
  } catch (error) {
    pinMessage.textContent = error.message;
    pinMessage.classList.add("error");
  }
}

pinForm.addEventListener("submit", (event) => {
  event.preventDefault();
  adminPin = pinInput.value.trim();
  localStorage.setItem("theBerberAdminPin", adminPin);
  loadAll();
});

bookingRows.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-status]");
  if (!button) return;
  try {
    await api(`/api/admin/bookings/${button.dataset.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: button.dataset.status }),
    });
    await loadSummary();
    await loadBookings();
  } catch (error) {
    pinMessage.textContent = error.message;
    pinMessage.classList.add("error");
  }
});

[bookingSearch, bookingDate, statusFilter].forEach((element) => {
  element.addEventListener("input", loadBookings);
});
customerSearch.addEventListener("input", loadCustomers);
refreshBookings.addEventListener("click", loadBookings);
refreshCustomers.addEventListener("click", loadCustomers);

bookingDate.value = todayIso();
if (adminPin) {
  pinInput.value = adminPin;
  loadAll();
}
