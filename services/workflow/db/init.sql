-- property_document_contents: in production this table is owned by the
-- shared kiosk-dashboard database (see app/models.py), not by this service.
-- It's created here only so `docker compose up` has something to query
-- against for local development/testing.
CREATE TABLE IF NOT EXISTS property_document_contents (
    id                   BIGSERIAL PRIMARY KEY,
    property_document_id BIGINT NOT NULL,
    device_id            VARCHAR(10) NOT NULL,
    content_html         TEXT NOT NULL,
    word_count           INTEGER NOT NULL,
    updated_by_agent_id  VARCHAR(10),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_property_document_contents_device_id
    ON property_document_contents (device_id);
CREATE INDEX IF NOT EXISTS idx_property_document_contents_updated_at
    ON property_document_contents (updated_at DESC);

-- sample seed data for local testing (safe to remove)
INSERT INTO property_document_contents
    (property_document_id, device_id, content_html, word_count, updated_by_agent_id)
VALUES
    (1, 'device-001',
     '<h1>Thermostat Manual</h1>'
     '<p>The thermostat supports schedules, <strong>eco mode</strong>, and remote control via the '
     'mobile app.</p>'
     '<h2>Reset instructions</h2>'
     '<p>To reset it, hold the power button for <strong>10 seconds</strong>.</p>'
     '<ul>'
     '<li>Eco mode reduces heating by 2 degrees during unoccupied hours</li>'
     '<li>Toggle it from Settings &gt; Eco Mode</li>'
     '</ul>',
     42, 'agent-01'),
    (2, 'device-001',
     '<h1>Thermostat Troubleshooting</h1>'
     '<p>If the thermostat display is blank, check the batteries first.</p>'
     '<p>If it is unresponsive after a firmware update, perform a factory reset via '
     '<em>Settings &gt; Advanced &gt; Factory Reset</em>.</p>',
     28, 'agent-01'),
    (3, 'device-002',
     '<h1>Camera Setup Guide</h1>'
     '<p>The security camera connects over <strong>2.4GHz Wi-Fi only</strong>.</p>'
     '<p>Pair it using the companion app QR scanner. Night vision activates automatically '
     'below 5 lux of ambient light.</p>',
     24, 'agent-02')
ON CONFLICT DO NOTHING;
