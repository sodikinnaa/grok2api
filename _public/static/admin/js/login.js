const apiKeyInput = document.getElementById('api-key-input');
const functionKeyInput = document.getElementById('function-key-input');
if (apiKeyInput) {
  apiKeyInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') login();
  });
}
if (functionKeyInput) {
  functionKeyInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') login();
  });
}

async function requestLogin(key) {
  const res = await fetch('/v1/admin/verify', {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${key}` }
  });
  return res.ok;
}

async function login() {
  const input = (apiKeyInput ? apiKeyInput.value : '').trim();
  const functionKey = (functionKeyInput ? functionKeyInput.value : '').trim();
  if (!input) return;

  try {
    const ok = await requestLogin(input);
    if (ok) {
      await storeAppKey(input);
      if (functionKey) {
        await storeFunctionKey(functionKey);
      }
      window.location.href = '/admin/token';
    } else {
      showToast(t('common.invalidKey'), 'error');
    }
  } catch (e) {
    showToast(t('common.connectionFailed'), 'error');
  }
}

// Auto-redirect checks
(async () => {
  const existingKey = await getStoredAppKey();
  if (!existingKey) return;
  try {
    const ok = await requestLogin(existingKey);
    if (ok) window.location.href = '/admin/token';
  } catch (e) {
    return;
  }
})();
