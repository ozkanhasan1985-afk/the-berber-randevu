const serviceGrid = document.querySelector("#serviceGrid");
const serviceSelect = document.querySelector("#serviceSelect");
const barberSelect = document.querySelector("#barberSelect");
const dateInput = document.querySelector("#dateInput");
const timeSelect = document.querySelector("#timeSelect");
const bookingForm = document.querySelector("#bookingForm");
const formMessage = document.querySelector("#formMessage");

let services = [];
let barbers = [];

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

async function loadSlots() {
  const serviceId = serviceSelect.value;
  const barberId = barberSelect.value;
  const day = dateInput.value;
  timeSelect.replaceChildren(option("", "Saat seç"));
  if (!serviceId || !barberId || !day) return;

  try {
    const params = new URLSearchParams({ service_id: serviceId, barber_id: barberId, date: day });
    const data = await api(`/api/slots?${params.toString()}`);
    if (data.slots.length === 0) {
      timeSelect.replaceChildren(option("", "Uygun saat kalmadı"));
      return;
    }
    timeSelect.replaceChildren(option("", "Saat seç"));
    data.slots.forEach((slot) => timeSelect.append(option(slot, slot)));
  } catch (error) {
    setMessage(error.message, true);
  }
}

async function init() {
  const data = await api("/api/bootstrap");
  services = data.services;
  barbers = data.barbers;
  dateInput.min = todayIso();
  dateInput.value = todayIso();
  renderServices();
  fillSelects();
}

bookingForm.addEventListener("submit", async (event) => {
  event.preventDefault();
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

init().catch((error) => setMessage(error.message, true));
