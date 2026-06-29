const serviceGrid = document.querySelector("#serviceGrid");
const serviceSelect = document.querySelector("#serviceSelect");
const barberSelect = document.querySelector("#barberSelect");
const dateInput = document.querySelector("#dateInput");
const timeInput = document.querySelector("#timeInput");
const timeGrid = document.querySelector("#timeGrid");
const bookingForm = document.querySelector("#bookingForm");
const formMessage = document.querySelector("#formMessage");
const contactTitle = document.querySelector("#contactTitle");
const contactAddress = document.querySelector("#contactAddress");
const contactPhone = document.querySelector("#contactPhone");
const contactEmail = document.querySelector("#contactEmail");

let services = [];
let barbers = [];
let contact = {};

function money(value) {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    maximumFractionDigits: 0,
  }).format(value);
}

function todayIso() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function setMessage(message, isError = false) {
  formMessage.textContent = message;
  formMessage.classList.toggle("error", isError);
}

function option(value, text) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = text;
  return item;
}

function renderTimePlaceholder(message) {
  timeInput.value = "";
  timeGrid.innerHTML = `<span class="time-placeholder">${message}</span>`;
}

function renderTimeSlots(slots) {
  timeInput.value = "";
  if (slots.length === 0) {
    renderTimePlaceholder("Uygun saat kalmadı");
    return;
  }

  timeGrid.innerHTML = slots
    .map(
      (slot) => `
        <button class="time-slot" type="button" role="option" aria-selected="false" data-time="${slot}">
          ${slot}
        </button>
      `,
    )
    .join("");
}

function openDatePicker() {
  if (typeof dateInput.showPicker !== "function") return;
  try {
    dateInput.showPicker();
  } catch (error) {
    // The picker may already be open in some browsers.
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "İşlem tamamlanamadı.");
  return data;
}

function renderServices() {
  serviceGrid.innerHTML = services
    .map(
      (service, index) => `
        <article class="service-card">
          <div>
            <small>${String(index + 1).padStart(2, "0")}</small>
            <h3>${service.name}</h3>
            <p>${service.duration} dakika</p>
          </div>
          <strong>${money(service.price)}</strong>
        </article>
      `,
    )
    .join("");
}

function fillSelects() {
  serviceSelect.replaceChildren(option("", "Hizmet seç"));
  barberSelect.replaceChildren(option("", "Berber seç"));
  services.forEach((service) => serviceSelect.append(option(service.id, `${service.name} - ${money(service.price)}`)));
  barbers.forEach((barber) => barberSelect.append(option(barber.id, `${barber.name} - ${barber.title}`)));
}

function renderContact() {
  contactTitle.textContent = contact.title || "THE BERBER";
  contactAddress.textContent = contact.address || "";
  contactPhone.href = `tel:${contact.phone || ""}`;
  contactEmail.href = `mailto:${contact.email || ""}`;
}

async function loadSlots() {
  const serviceId = serviceSelect.value;
  const barberId = barberSelect.value;
  const day = dateInput.value;
  renderTimePlaceholder("Saatler yükleniyor...");
  if (!serviceId || !barberId || !day) {
    renderTimePlaceholder("Önce hizmet, berber ve gün seç");
    return;
  }

  try {
    const params = new URLSearchParams({ service_id: serviceId, barber_id: barberId, date: day });
    const data = await api(`/api/slots?${params.toString()}`);
    renderTimeSlots(data.slots);
  } catch (error) {
    renderTimePlaceholder("Saatler alınamadı");
    setMessage(error.message, true);
  }
}

async function init() {
  const data = await api("/api/bootstrap");
  services = data.services;
  barbers = data.barbers;
  contact = data.contact || {};
  dateInput.min = todayIso();
  dateInput.value = todayIso();
  renderServices();
  fillSelects();
  renderContact();
}

bookingForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!timeInput.value) {
    setMessage("Lütfen bir saat kutucuğu seç.", true);
    return;
  }
  setMessage("Randevu oluşturuluyor...");
  const payload = Object.fromEntries(new FormData(bookingForm).entries());
  try {
    const data = await api("/api/bookings", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    bookingForm.reset();
    dateInput.value = todayIso();
    await loadSlots();
    setMessage(`Randevun alındı. Takip kodun: ${data.booking.id}`);
  } catch (error) {
    setMessage(error.message, true);
  }
});

[serviceSelect, barberSelect, dateInput].forEach((element) => {
  element.addEventListener("change", loadSlots);
});

dateInput.addEventListener("focus", openDatePicker);
dateInput.addEventListener("click", openDatePicker);

timeGrid.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-time]");
  if (!button) return;
  timeInput.value = button.dataset.time;
  timeGrid.querySelectorAll(".time-slot").forEach((slot) => {
    const selected = slot === button;
    slot.classList.toggle("selected", selected);
    slot.setAttribute("aria-selected", selected ? "true" : "false");
  });
});

init().catch((error) => setMessage(error.message, true));
