const express = require('express');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

const app = express();
app.use(express.json());

let isReady = false;

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--unhandled-rejections=strict']
    }
});

client.on('qr', (qr) => {
    console.log('Scan this QR code with your WhatsApp app:');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    isReady = true;
    console.log('WhatsApp Web Client is ready!');
});

client.on('disconnected', (reason) => {
    isReady = false;
    console.log('WhatsApp Web Client disconnected:', reason);
});

// Health check endpoint for message.py
app.get('/health', (req, res) => {
    res.json({ status: 'ok', ready: isReady });
});

app.post('/send-message', async (req, res) => {
    if (!isReady) {
        return res.status(503).json({ error: 'WhatsApp client is still initializing.' });
    }

    const { phone, message } = req.body;
    if (!phone || !message) {
        return res.status(400).json({ error: 'phone and message are required' });
    }

    try {
        let cleanPhone = phone.replace(/[^\d]/g, '');
        if (cleanPhone.length === 10) {
            cleanPhone = `91${cleanPhone}`; // Default to India country code
        }

        // Query WhatsApp Web to resolve the actual contact JID
        const numberDetails = await client.getNumberId(cleanPhone);

        if (!numberDetails) {
            console.warn(`[WA Warn] ${cleanPhone} is not registered on WhatsApp.`);
            return res.status(400).json({ 
                error: `Phone number +${cleanPhone} is not registered on WhatsApp.` 
            });
        }

        // Send message using verified serialized JID
        await client.sendMessage(numberDetails._serialized, message);
        console.log(`[WA] Sent to ${cleanPhone}`);
        res.json({ status: 'success' });
    } catch (err) {
        console.error('[WA Error]:', err.message);
        res.status(500).json({ error: err.toString() });
    }
});

client.initialize();
app.listen(3000, () => console.log('WhatsApp bridge listening on port 3000'));