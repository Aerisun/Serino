const STORAGE_KEY = "aerisun:subscription-emails";

function normalizeEmail(value: string) {
  return value.trim().toLowerCase();
}

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function getTrackedSubscriptionEmails() {
  if (!canUseStorage()) {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }

    return Array.from(
      new Set(
        parsed
          .map((item) => (typeof item === "string" ? normalizeEmail(item) : ""))
          .filter(Boolean),
      ),
    );
  } catch {
    return [];
  }
}

function saveTrackedSubscriptionEmails(emails: string[]) {
  if (!canUseStorage()) {
    return;
  }

  const normalized = Array.from(new Set(emails.map(normalizeEmail).filter(Boolean)));
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
}

export function trackSubscriptionEmail(email: string) {
  const current = getTrackedSubscriptionEmails();
  saveTrackedSubscriptionEmails([...current, email]);
}

export function untrackSubscriptionEmail(email: string) {
  const normalized = normalizeEmail(email);
  saveTrackedSubscriptionEmails(getTrackedSubscriptionEmails().filter((item) => item !== normalized));
}

export function replaceTrackedSubscriptionEmails(emails: string[]) {
  saveTrackedSubscriptionEmails(emails);
}
