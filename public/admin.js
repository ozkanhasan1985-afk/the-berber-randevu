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
const barberForm = document.querySelector("#barberForm");
const barberNameInput = document.querySelector("#barberNameInput");
const barberTitleInput = document.querySelector("#barberTitleInput");
const barberGrid = document.querySelector("#barberGrid");
const serviceForm = document.querySelector("#serviceForm");
const serviceIdInput = document.querySelector("#serviceIdInput");
const serviceNameInput = document.querySelector("#serviceNameInput");
const serviceDurationInput = document.querySelector("#serviceDurationInput");
const servicePriceInput = document.querySelector("#servicePriceInput");
const serviceSubmitButton = document.querySelector("#serviceSubmitButton");
const serviceCancelButton = document.querySelector("#serviceCancelButton");
const serviceAdminGrid = document.querySelector("#serviceAdminGrid");
const contactForm = document.querySelector("#contactForm");
const contactTitleInput = document.querySelector("#contactTitleInput");
const contactAddressInput = document.querySelector("#contactAddressInput");
const contactPhoneInput = document.querySelector("#contactPhoneInput");
const contactEmailInput = document.querySelector("#contactEmailInput");

const labels = {
  pending: "Bekliyor",
  confirmed: "Onaylandı",
  completed: "Tamamlandı",
  cancelled: "İptal",
  no_show: "Gelmedi",
};

let adminPin = localStorage.getItem("theBerberAdminPin") || "";
let knownPendingBookingIds = new Set();
let firstNotificationScan = true;
let bookingWatcher = null;

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

function renderBarbers(barbers) {
  if (barbers.length === 0) {
    barberGrid.innerHTML = `<article class="customer-card"><p>Berber bulunamadı.</p></article>`;
    return;
  }
  barberGrid.innerHTML = barbers
    .map(
      (barber) => `
        <article class="barber-card ${barber.active ? "" : "inactive"}">
          <div>
            <h3>${escapeHtml(barber.name)}</h3>
            <p>${escapeHtml(barber.title)}</p>
          </div>
          <div class="customer-meta">
            <span>Aktif</span>
            <button class="small-button danger-button" data-barber-id="${barber.id}" type="button">Sil</button>
          </div>
        </article>
      `,
    )
    .join("");
}

function money(value) {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    maximumFractionDigits: 0,
  }).format(value);
}

function resetServiceForm() {
  serviceForm.reset();
  serviceIdInput.value = "";
  serviceSubmitButton.textContent = "Hizmet Ekle";
  serviceCancelButton.hidden = true;
}

function renderServices(services) {
  if (services.length === 0) {
    serviceAdminGrid.innerHTML = `<article class="service-admin-card"><p>Hizmet bulunamadı.</p></article>`;
    return;
  }
  serviceAdminGrid.innerHTML = services
    .map(
      (service) => `
        <article class="service-admin-card">
          <div>
            <h3>${escapeHtml(service.name)}</h3>
            <p>${service.duration} dakika<br>${money(service.price)}</p>
          </div>
          <div class="action-row">
            <button
              class="small-button"
              data-service-edit="${service.id}"
              data-service-name="${escapeHtml(service.name)}"
              data-service-duration="${service.duration}"
              data-service-price="${service.price}"
              type="button"
            >Düzenle</button>
            <button class="small-button danger-button" data-service-delete="${service.id}" type="button">Sil</button>
          </div>
        </article>
      `,
    )
    .join("");
}

function fillContactForm(contact) {
  contactTitleInput.value = contact.title || "";
  contactAddressInput.value = contact.address || "";
  contactPhoneInput.value = contact.phone || "";
  contactEmailInput.value = contact.email || "";
}

function showBookingToast(booking) {
  let container = document.querySelector("#bookingToastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "bookingToastContainer";
    container.className = "toast-container";
    document.body.append(container);
  }

  const toast = document.createElement("article");
  toast.className = "booking-toast";
  toast.innerHTML = `
    <strong>Yeni randevu</strong>
    <span>${escapeHtml(booking.customer_name)} - ${escapeHtml(booking.service_name)}</span>
    <small>${booking.date} / ${booking.time}</small>
  `;
  container.prepend(toast);
  setTimeout(() => toast.remove(), 30000);
}

async function checkNewBookings() {
  if (!adminPin) return;
  try {
    const data = await api("/api/admin/bookings?status=pending");
    const currentIds = new Set(data.bookings.map((booking) => booking.id));
    if (firstNotificationScan) {
      knownPendingBookingIds = currentIds;
      firstNotificationScan = false;
      return;
    }

    const newBookings = data.bookings.filter((booking) => !knownPendingBookingIds.has(booking.id));
    newBookings.forEach(showBookingToast);
    knownPendingBookingIds = currentIds;
    if (newBookings.length > 0) {
      await loadSummary();
      await loadBookings();
      await loadCustomers();
    }
  } catch (error) {
    pinMessage.textContent = error.message;
    pinMessage.classList.add("error");
  }
}

async function startBookingWatcher() {
  firstNotificationScan = true;
  knownPendingBookingIds = new Set();
  if (bookingWatcher) clearInterval(bookingWatcher);
  await checkNewBookings();
  bookingWatcher = setInterval(checkNewBookings, 8000);
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

async function loadBarbers() {
  const data = await api("/api/admin/barbers");
  renderBarbers(data.barbers);
}

async function loadServices() {
  const data = await api("/api/admin/services");
  renderServices(data.services);
}

async function loadContact() {
  const data = await api("/api/admin/contact");
  fillContactForm(data.contact);
}

async function loadAll() {
  try {
    pinMessage.textContent = "Panel yükleniyor...";
    await loadSummary();
    await loadServices();
    await loadBarbers();
    await loadContact();
    await loadBookings();
    await loadCustomers();
    await startBookingWatcher();
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

serviceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const serviceId = serviceIdInput.value;
  const payload = {
    name: serviceNameInput.value.trim(),
    duration: serviceDurationInput.value,
    price: servicePriceInput.value,
  };
  try {
    pinMessage.textContent = serviceId ? "Hizmet güncelleniyor..." : "Hizmet ekleniyor...";
    await api(serviceId ? `/api/admin/services/${serviceId}` : "/api/admin/services", {
      method: serviceId ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    resetServiceForm();
    await loadServices();
    pinMessage.textContent = serviceId ? "Hizmet güncellendi." : "Hizmet eklendi.";
    pinMessage.classList.remove("error");
  } catch (error) {
    pinMessage.textContent = error.message;
    pinMessage.classList.add("error");
  }
});

serviceCancelButton.addEventListener("click", resetServiceForm);

serviceAdminGrid.addEventListener("click", async (event) => {
  const editButton = event.target.closest("button[data-service-edit]");
  const deleteButton = event.target.closest("button[data-service-delete]");
  if (editButton) {
    serviceIdInput.value = editButton.dataset.serviceEdit;
    serviceNameInput.value = editButton.dataset.serviceName;
    serviceDurationInput.value = editButton.dataset.serviceDuration;
    servicePriceInput.value = editButton.dataset.servicePrice;
    serviceSubmitButton.textContent = "Hizmeti Güncelle";
    serviceCancelButton.hidden = false;
    serviceNameInput.focus();
    return;
  }
  if (!deleteButton) return;
  try {
    await api(`/api/admin/services/${deleteButton.dataset.serviceDelete}`, { method: "DELETE" });
    resetServiceForm();
    await loadServices();
    pinMessage.textContent = "Hizmet silindi.";
    pinMessage.classList.remove("error");
  } catch (error) {
    pinMessage.textContent = error.message;
    pinMessage.classList.add("error");
  }
});

contactForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    pinMessage.textContent = "İletişim kaydediliyor...";
    await api("/api/admin/contact", {
      method: "PATCH",
      body: JSON.stringify({
        title: contactTitleInput.value.trim(),
        address: contactAddressInput.value.trim(),
        phone: contactPhoneInput.value.trim(),
        email: contactEmailInput.value.trim(),
      }),
    });
    pinMessage.textContent = "İletişim kaydedildi.";
    pinMessage.classList.remove("error");
  } catch (error) {
    pinMessage.textContent = error.message;
    pinMessage.classList.add("error");
  }
});

barberForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    pinMessage.textContent = "Berber ekleniyor...";
    await api("/api/admin/barbers", {
      method: "POST",
      body: JSON.stringify({
        name: barberNameInput.value.trim(),
        title: barberTitleInput.value.trim(),
      }),
    });
    barberForm.reset();
    await loadBarbers();
    pinMessage.textContent = "Berber eklendi.";
    pinMessage.classList.remove("error");
  } catch (error) {
    pinMessage.textContent = error.message;
    pinMessage.classList.add("error");
  }
});

barberGrid.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-barber-id]");
  if (!button) return;
  try {
    await api(`/api/admin/barbers/${button.dataset.barberId}`, { method: "DELETE" });
    await loadBarbers();
    pinMessage.textContent = "Berber silindi.";
    pinMessage.classList.remove("error");
  } catch (error) {
    pinMessage.textContent = error.message;
    pinMessage.classList.add("error");
  }
});

bookingDate.value = todayIso();
if (adminPin) {
  pinInput.value = adminPin;
  loadAll();
}
