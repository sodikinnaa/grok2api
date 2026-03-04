const publicKeyInput = document.getElementById('public-key-input');
if (publicKeyInput) {
  publicKeyInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') login();
  });
}

async function requestPublicLogin(key) {
  const headers = key ? { 'Authorization': `Bearer ${key}` } : {};
  const res = await fetch('/v1/public/verify', {
    method: 'GET',
    headers
  });
  return res.ok;
}

async function login() {
  const input = (publicKeyInput ? publicKeyInput.value : '').trim();
  try {
    const ok = await requestPublicLogin(input);
    if (ok) {
      await storePublicKey(input);
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
    const stored = await getStoredPublicKey();
    if (stored) {
      const ok = await requestPublicLogin(stored);
      if (ok) {
        window.location.href = '/chat';
        return;
      }
      clearStoredPublicKey();
    }

    const ok = await requestPublicLogin('');
    if (ok) {
      window.location.href = '/chat';
    }
  } catch (e) {
    return;
  }
})();
