export async function provisionTelnyxNumber(phone) {
  const response = fetch("/api/rootcall/provision", ...
 {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ phone }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Provisioning failed");
  }

  return await response.json();
}
