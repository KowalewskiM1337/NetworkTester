// Główny adres backendu FastAPI
const API_URL = "http://127.0.0.1:8000";

// Pobranie listy serwerów z bazy
function pobierzHosty() {
  // Wymuszamy ominięcie cache przeglądarki { cache: "no-store" }
  fetch(API_URL + "/hosts", { cache: "no-store" })
    .then(function (odpowiedz) {
      return odpowiedz.json();
    })
    .then(function (dane) {
      console.log("Pobrane hosty z bazy:", dane);

      // Celujemy bezpośrednio w ciało tabeli, chroniąc nagłówek
      var tbody = document.querySelector("tbody");
      tbody.innerHTML = "";

      for (var i = 0; i < dane.length; i++) {
        var host = dane[i];
        var wiersz = tbody.insertRow();

        wiersz.insertCell(0).innerText = host.name;
        wiersz.insertCell(1).innerText = host.target;
        wiersz.insertCell(2).innerText = host.check_type;

        // Komórka na status
        var komorkaStatus = wiersz.insertCell(3);
        komorkaStatus.id = "status-" + host.id;
        komorkaStatus.innerText = "Nie sprawdzono";

        // Komórka na czas odpowiedzi
        var komorkaCzas = wiersz.insertCell(4);
        komorkaCzas.id = "czas-" + host.id;
        komorkaCzas.innerText = "-";

        // Przycisk Sprawdź i Usuń
        var komorkaAkcja = wiersz.insertCell(5);

        var przyciskSprawdz = document.createElement("button");
        przyciskSprawdz.innerText = "Sprawdź";
        przyciskSprawdz.className = "btn-outline";
        przyciskSprawdz.style.marginRight = "8px";
        przyciskSprawdz.onclick = (function (id) {
          return function () {
            sprawdzHost(id);
          };
        })(host.id);

        var przyciskUsun = document.createElement("button");
        przyciskUsun.innerText = "Usuń";
        przyciskUsun.className = "btn-outline";
        przyciskUsun.style.color = "var(--danger-color)";
        przyciskUsun.style.borderColor = "var(--danger-color)";
        przyciskUsun.onclick = (function (id) {
          return function () {
            if (
              confirm("Czy na pewno chcesz usunąć ten serwer z monitoringu?")
            ) {
              usunHost(id);
            }
          };
        })(host.id);

        komorkaAkcja.appendChild(przyciskSprawdz);
        komorkaAkcja.appendChild(przyciskUsun);
      }
    })
    .catch(function (err) {
      console.error("Błąd backendu (uvicorn nie działa lub błąd MySQL):", err);
    });
}

// Dodawanie nowego hosta
function dodajHost() {
  var nazwa = document.getElementById("nazwa").value;
  var adres = document.getElementById("adres").value;
  var typ = document.getElementById("typ").value;

  if (!nazwa || !adres) {
    alert("Podaj nazwę i adres celu!");
    return;
  }

  var payload = {
    name: nazwa,
    target: adres,
    check_type: typ,
    interval_seconds: 60,
  };

  fetch(API_URL + "/hosts", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  })
    .then(function (odpowiedz) {
      if (odpowiedz.ok) {
        // Czyszczenie inputów po udanym dodaniu
        document.getElementById("nazwa").value = "";
        document.getElementById("adres").value = "";
        pobierzHosty();
      } else {
        alert("Błąd podczas dodawania celu.");
      }
    })
    .catch(function (err) {
      console.error("Błąd przy dodawaniu:", err);
    });
}

// Wywołanie testu dla danego hosta
function sprawdzHost(id) {
  var komorkaStatus = document.getElementById("status-" + id);
  var komorkaCzas = document.getElementById("czas-" + id);

  komorkaStatus.innerText = "Badanie...";
  komorkaStatus.className = "";
  komorkaCzas.innerText = "-";

  fetch(API_URL + "/hosts/" + id + "/check", {
    method: "POST",
  })
    .then(function (odpowiedz) {
      return odpowiedz.json();
    })
    .then(function (dane) {
      if (dane.status === "UP") {
        komorkaStatus.innerText = "ONLINE";
        komorkaStatus.className = "status-up";
      } else {
        komorkaStatus.innerText = "OFFLINE";
        komorkaStatus.className = "status-down";
      }
      komorkaCzas.innerText = dane.response_time_ms + " ms";
    })
    .catch(function (err) {
      komorkaStatus.innerText = "BŁĄD";
      komorkaStatus.className = "status-down";
      console.error("Błąd testu:", err);
    });
}

// Usuwanie hosta (soft delete)
function usunHost(id) {
  fetch(API_URL + "/hosts/" + id, {
    method: "DELETE",
  })
    .then(function (odpowiedz) {
      if (odpowiedz.ok) {
        pobierzHosty(); // Odświeżamy tabelę, zniknie z niej usunięty host
      } else {
        console.error("Błąd podczas usuwania hosta:", odpowiedz.status);
        alert("Nie udało się usunąć hosta.");
      }
    })
    .catch(function (err) {
      console.error("Błąd sieci przy usuwaniu:", err);
    });
}
