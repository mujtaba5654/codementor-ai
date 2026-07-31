async function loadUsage() {
  const res = await fetch('/api/usage');
  const data = await res.json();

  document.getElementById('totalRequests').textContent = data.total_requests;
  document.getElementById('totalTokens').textContent = data.total_tokens.toLocaleString();
  document.getElementById('ioTokens').textContent =
    `${data.total_input_tokens.toLocaleString()} / ${data.total_output_tokens.toLocaleString()}`;
  document.getElementById('totalCost').textContent = `$${data.total_cost_usd.toFixed(6)}`;

  const sessionBody = document.querySelector('#sessionTable tbody');
  sessionBody.innerHTML = '';
  data.sessions.forEach(s => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${s.session_id}</td>
      <td>${s.user_name}</td>
      <td>${s.requests}</td>
      <td>${s.input_tokens.toLocaleString()}</td>
      <td>${s.output_tokens.toLocaleString()}</td>
      <td>$${s.total_cost.toFixed(6)}</td>
    `;
    sessionBody.appendChild(row);
  });

  const recentBody = document.querySelector('#recentTable tbody');
  recentBody.innerHTML = '';
  data.recent_requests.forEach(r => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${r.id}</td>
      <td>${r.session_id}</td>
      <td>${r.model_name}</td>
      <td>${r.input_tokens}</td>
      <td>${r.output_tokens}</td>
      <td>${r.total_tokens}</td>
      <td>$${r.estimated_cost_usd.toFixed(6)}</td>
      <td>${r.created_at}</td>
    `;
    recentBody.appendChild(row);
  });
}

loadUsage();