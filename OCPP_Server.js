const { WebSocketServer } = require('ws');
const readline = require('readline');

const wss = new WebSocketServer({ 
    port: 8080,
    handleProtocols: (protocols) => protocols.has('ocpp1.6') ? 'ocpp1.6' : false
});

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

const PRICE_PER_KWH = 0.25; //Placeholder Price, can be changed

console.log("🚀 CSMS Online. Waiting for chargers...");

wss.on('connection', (ws, req) => {
    const chargerId = req.url.split('/').pop();
    console.log(`\n✅ [${chargerId}] Connected!`);

    console.log(`\n--- COMMANDS ---`);
    console.log("Type '1' -> Start | Type '3' -> Stop");
    console.log("Type 'limit <number>' -> e.g., 'limit 10' or 'limit 32'");
    console.log("------------------------------------------");

    rl.on('line', (input) => {
        let command = null;
        const uniqueId = "server-" + Math.floor(Math.random() * 1000);
        const args = input.split(' ');

        if (input === '1') {
            command = [2, uniqueId, "RemoteStartTransaction", { idTag: "Charger_01" }];
            console.log("📤 Sending: Remote Start...");
        } 
			else if (args[0] === 'limit') {
				const ampValue = parseFloat(args[1]);
				if (!isNaN(ampValue)) {
					command = [2, uniqueId, "SetChargingProfile", {
						connectorId: 1,
						csChargingProfiles: { 
							chargingProfileId: 1, 
							stackLevel: 0,
							chargingProfilePurpose: 'TxProfile',
							chargingProfileKind: 'Relative',
							chargingSchedule: { 
								chargingRateUnit: 'A',
								chargingSchedulePeriod: [{ startPeriod: 0, limit: ampValue }] 
							}
						}
					}];
					console.log(`📤 Sending: Set Power Limit to ${ampValue}A...`);
				} else {
					console.log("❌ Invalid limit. Use 'limit 16'");
				}
			}
        else if (input === '3') {
            command = [2, uniqueId, "RemoteStopTransaction", { transactionId: 123 }];
            console.log("📤 Sending: Remote Stop...");
        }

        if (command) ws.send(JSON.stringify(command));
    });

    ws.on('message', (data) => {
        const [type, id, action, payload] = JSON.parse(data);
        
        if (type === 2) {
            let res = {};
            const now = new Date().toISOString();

            if (action === 'BootNotification') {
                res = { status: 'Accepted', currentTime: now, interval: 60 };
            } 
            else if (action === 'Heartbeat') {
                res = { currentTime: now };
            }
            else if (action === 'MeterValues') {
				const sampled = payload.meterValue[0].sampledValue;
				const whValue = parseFloat(sampled[0].value);
				const currentAmps = sampled[1] ? sampled[1].value : ""; 
				const kwh = whValue / 1000;
				const cost = kwh * PRICE_PER_KWH;

				console.clear();
				console.log(`\x1b[32m==========================================\x1b[0m`);
				console.log(`\x1b[1m⚡ TERMINAL: ${chargerId}\x1b[0m`);
				console.log(`\x1b[32m==========================================\x1b[0m`);
				console.log(`  STATUS:       \x1b[33mCHARGING\x1b[0m`);
				console.log(`  CURRENT DRAW: \x1b[36m${currentAmps} Amperes\x1b[0m`);
				console.log(`  TOTAL ENERGY: ${kwh.toFixed(3)} kWh`);
				console.log(`  SESSION COST: \x1b[32m$${cost.toFixed(2)}\x1b[0m`);
				console.log(`\x1b[32m==========================================\x1b[0m`);
				console.log(` > limit <n> | > 3 (Stop) | > stress`);

				res = {}; 
			}
            else if (action === 'StartTransaction') {
                res = {
                    transactionId: Math.floor(Math.random() * 1000),
                    idTagInfo: { status: 'Accepted' }
                };
            }

            ws.send(JSON.stringify([3, id, res]));
        }
    });

    ws.on('close', () => console.log(`❌ [${chargerId}] Disconnected.`));
});