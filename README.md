# ocpp-1.6-smart-charging-simulator
OCPP 1.6 CSMS + Charge Point simulator with smart charging support

# OCPP 1.6 Smart Charging Simulator

This project simulates a full OCPP 1.6 environment:

- Node.js CSMS (Central System)
- Python Charge Point
- Remote start/stop transactions
- Live meter values
- Dynamic current limiting (SetChargingProfile)

## 🚀 Features
- RemoteStartTransaction / RemoteStopTransaction
- Heartbeat & BootNotification
- MeterValues simulation
- Smart charging (limit current via CLI)

## 🛠️ How to run

### 1. Start CSMS (Node.js)
```bash
npm install ws
node server.js
```
### 2. Start Charge Point (Python)
```bash
pip install ocpp websockets
python charger.py
```
### 3. Commands
```bash
1 → Start charging
limit 16 → Set current limit
3 → Stop charging
```
