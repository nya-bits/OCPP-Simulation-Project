import asyncio
import datetime
import logging
import argparse
import websockets
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call, call_result
from ocpp.v16.enums import Action, RegistrationStatus, ConfigurationStatus, RemoteStartStopStatus

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ChargePoint")

class SmartCharger(CP):
    def __init__(self, id, connection, vendor="Energy", model="Pro-1"):
        super().__init__(id, connection)
        self.vendor = vendor
        self.model = model
        self.transaction_id = None
        self.meter_value = 0
        self.current_limit = 32.0 

    # SERVER COMMANDS (Only "Limit" is implemented in conjunction with the server)
    @on("SetChargingProfile")
    async def on_set_profile(self, connector_id, cs_charging_profiles, **kwargs):
        try:
            schedule = cs_charging_profiles.get('charging_schedule') or cs_charging_profiles.get('chargingSchedule')
            
            if not schedule:
                logger.error("❌ Schedule not found in payload")
                return call_result.SetChargingProfile(status=ConfigurationStatus.rejected)

            periods = schedule.get('charging_schedule_period') or schedule.get('chargingSchedulePeriod')

            if not periods or len(periods) == 0:
                logger.error("❌ No charging periods found")
                return call_result.SetChargingProfile(status=ConfigurationStatus.rejected)

            # 3. Limiting the Current (Amps)
            new_limit = float(periods[0]['limit'])
            self.current_limit = new_limit
            
            logger.info(f"⚡ [SMART] Power Throttled to: {self.current_limit}A")
            return call_result.SetChargingProfile(status=ConfigurationStatus.accepted)

        except Exception as e:
            logger.error(f"❌ Failed to set profile: {e}")
            return call_result.SetChargingProfile(status=ConfigurationStatus.rejected)

    @on("RemoteStartTransaction")
    async def on_remote_start(self, id_tag, **kwargs):
        logger.info(f"📥 Remote Start Command for Tag: {id_tag}")
        asyncio.create_task(self.start_charging(id_tag))
        return call_result.RemoteStartTransaction(status=RemoteStartStopStatus.accepted)

    @on("RemoteStopTransaction")
    async def on_remote_stop(self, transaction_id, **kwargs):
        logger.info(f"🛑 Remote Stop Command for Transaction: {transaction_id}")
        self.transaction_id = None 
        return call_result.RemoteStopTransaction(status=RemoteStartStopStatus.accepted)

    # Heartbeat
    async def heartbeat_loop(self, interval=30):
        while True:
            await self.call(call.Heartbeat())
            logger.info("💓 Heartbeat Sent")
            await asyncio.sleep(interval)

    async def meter_loop(self):
        while True:
            if self.transaction_id:
                # Watt Hour Calculation
                current_limit_float = float(self.current_limit)
                increment = (current_limit_float * 240 * 5) / 3600
                self.meter_value += increment
                
                now = datetime.datetime.now(datetime.UTC).isoformat() + "Z"
                
                await self.call(call.MeterValues(
                    connector_id=1,
                    transaction_id=self.transaction_id,
                    meter_value=[{
                        "timestamp": now,
                        "sampled_value": [
                            {"value": str(round(self.meter_value, 2)), "unit": "Wh"},
                            {"value": str(current_limit_float), "unit": "A"} 
                        ]
                    }]
                ))
            await asyncio.sleep(5)

    # Actions
    async def start_charging(self, id_tag):
        if self.transaction_id:
            logger.warning("Transaction already in progress.")
            return

        now = datetime.datetime.now(datetime.UTC).isoformat() + "Z"
        request = call.StartTransaction(
            connector_id=1, id_tag=id_tag, meter_start=self.meter_value, timestamp=now
        )
        
        try:
            response = await self.call(request)
            self.transaction_id = response.transaction_id
            logger.info(f"🚀 Transaction Started! ID: {self.transaction_id}")
        except Exception as e:
            logger.error(f"Failed to start transaction: {e}")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--id", default="ChargePoint_01")
    parser.add_argument("-H", "--host", default="localhost")
    parser.add_argument("-p", "--port", default=8080, type=int)
    args = parser.parse_args()

    url = f"ws://{args.host}:{args.port}/{args.id}"
    
    try:
        async with websockets.connect(url, subprotocols=["ocpp1.6"]) as ws:
            charger = SmartCharger(args.id, ws)
            logger.info(f"🔌 Connected to CSMS at {url}")

            await asyncio.gather(
                charger.start(), 
                charger.heartbeat_loop(),
                charger.meter_loop(),
                charger.call(call.BootNotification(
                    charge_point_vendor=charger.vendor, 
                    charge_point_model=charger.model
                ))
            )
    except Exception as e:
        logger.error(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass