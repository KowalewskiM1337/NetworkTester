const API = "http://127.0.0.1:8000";

// Pobieranie listy serwerów z bazy i wstawianie do tabeli
async function pobierzHosty() {
  let odpowiedz = await fetch(API + "/hosts");
  let hosty = await odpowiedz.json();

  let tabela = document.getElementById("lista-hostow");
  tabela.innerHTML = "";

  for (let host of hosty) {
    let wiersz = document.createElement("tr");

    wiersz.innerHTML = `
            <td>${host.name}</td>
            <td>${host.target}</td>
            <td>${host.check_type}</td>
            <td id="status-${host.id}">Nieznany</td>
            <td id="czas-${host.id}">-</td>
            <td>
                <button onclick="sprawdzHost(${host.id})">Sprawdź</button>
            </td>
        `;

    tabela.appendChild(wiersz);
  }
}

// Dodawanie nowego hosta przez formularz
async function dodajHost() {
  let nazwa = document.getElementById("nazwa").value;
  let adres = document.getElementById("adres").value;
  let typ = document.getElementById("typ").value;

  if (!nazwa || !adres) {
    alert("Wpisz nazwę i adres!");
    return;
  }

  let dane = {
    name: nazwa,
    target: adres,
    check_type: typ,
    port: null,
    interval_seconds: 60,
  };

  await fetch(API + "/hosts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dane),
  });

  document.getElementById("nazwa").value = "";
  document.getElementById("adres").value = "";
  pobierzHosty();
}

// Uruchomienie testu diagnostycznego dla wskazanego hosta
async function sprawdzHost(id) {
  let poleStatus = document.getElementById("status-" + id);
  let poleCzas = document.getElementById("czas-" + id);

  poleStatus.innerText = "Badanie...";

  let odpowiedz = await fetch(API + "/hosts/" + id + "/check", {
    method: "POST",
  });
  let wynik = await odpowiedz.json();

  if (wynik.status === "UP") {
    poleStatus.innerHTML = '<span class="online">ONLINE</span>';
  } else {
    poleStatus.innerHTML = '<span class="offline">OFFLINE</span>';
  }

  poleCzas.innerText = wynik.response_time_ms + " ms";
}

// Załaduj hosty po uruchomieniu pliku
pobierzHosty();
