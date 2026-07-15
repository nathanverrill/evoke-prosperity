const learnerId = "learner_demo_user";
const missionId = "mission_climate_resilience";

async function submitEvokeEvidence() {
  const fileInput = document.getElementById("evidenceFile");
  if (fileInput.files.length === 0) {
    alert("Please drop in a PDF asset file first.");
    return;
  }

  document.getElementById("stream-out").innerText =
    "Uploading payload and broadcasting event context...";

  const formData = new FormData();
  formData.append("learner_id", learnerId);
  formData.append("mission_id", missionId);
  formData.append("file", fileInput.files[0]);

  try {
    const res = await fetch("/api/submit-evidence", {
      method: "POST",
      body: formData,
    });
    const payload = await res.json();

    document.getElementById("stream-out").innerText = JSON.stringify(
      payload.event,
      null,
      2,
    );
    pollReadModel();
  } catch (err) {
    document.getElementById("stream-out").innerText = "Error: " + err.message;
  }
}

let pollCount = 0;
function pollReadModel() {
  pollCount = 0;
  const interval = setInterval(async () => {
    pollCount++;
    try {
      const res = await fetch(`/api/timeline/${learnerId}/${missionId}`);
      const data = await res.json();

      let htmlOutput = ``;

      if (data.timeline && data.timeline.length > 0) {
        htmlOutput += `<ul class="v-timeline">`;

        data.timeline.forEach((step) => {
          let timeStr = step.timestamp
            ? new Date(step.timestamp).toLocaleTimeString()
            : "";
          let icon = "✓";
          if (step.status === "active") icon = "●";
          if (step.status === "pending") icon = "○";

          htmlOutput += `
                        <li class="v-item ${step.status}">
                            <div class="v-marker">${icon}</div>
                            <div class="v-meta">
                                <div class="v-title">${step.title}</div>
                                ${timeStr ? `<div class="v-time">${timeStr}</div>` : ""}
                            </div>
                            <div class="v-body">
                                ${step.content ? step.content : "Pending upstream system execution triggers..."}
                            </div>
                        </li>
                    `;
        });

        htmlOutput += `</ul>`;
        document.getElementById("readmodel-out").innerHTML = htmlOutput;
      }

      if (data.status === "AI Feedback Ready" || pollCount > 20) {
        clearInterval(interval);
      }
    } catch (e) {
      console.log("Polling read model details layout error:", e);
    }
  }, 1500);
}

async function checkHealth(url, outId) {
  try {
    const r = await fetch(url);
    const d = await r.json();
    document.getElementById(outId).innerText = JSON.stringify(d, null, 2);
  } catch (e) {
    document.getElementById(outId).innerText =
      "Error linking infra: " + e.message;
  }
}
