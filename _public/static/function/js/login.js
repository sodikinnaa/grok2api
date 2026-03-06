const functionKeyInput = document.getElementById('function-key-input');
if (functionKeyInput) {
  functionKeyInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') login();
  });
}

async function requestFunctionLogin(key) {
  const headers = key ? { 'Authorization': `Bearer ${key}` } : {};
  const res = await fetch('/v1/function/verify', {
    method: 'GET',
    headers
  });
  return res.ok;
}

async function login() {
  const input = (functionKeyInput ? functionKeyInput.value : '').trim();
  try {
    const ok = await requestFunctionLogin(input);
    if (ok) {
      await storeFunctionKey(input);
      window.location.href = '/chat';
    } else {
      showToast(t('common.invalidKey'), 'error');
    }
  } catch (e) {
    showToast(t('common.connectionFailed'), 'error');
  }
}

(async () => {
  try {
    const stored = await getStoredFunctionKey();
    if (stored) {
      const ok = await requestFunctionLogin(stored);
      if (ok) {
        window.location.href = '/chat';
        return;
      }
      clearStoredFunctionKey();
    }

    const ok = await requestFunctionLogin('');
    if (ok) {
      window.location.href = '/chat';
    }
  } catch (e) {
    return;
  }
})();
