#!/usr/bin/env python
"""
Test Script for 5 Scalping Operations in Paper Mode.

This script connects to IB Gateway and executes 5 scalping operations
(market buy followed by market sell) to validate the trading agent's
ability to execute real trades in paper trading mode.

Configuration:
- Host: 127.0.0.1
- Port: 4002
- Mode: Paper Trading

Prerequisites:
1. IB Gateway must be running (either locally or via SSH tunnel)
2. SSH tunnel must be active: ssh -L 4002:127.0.0.1:4002 user@vps
3. Paper trading account must be logged in

Usage:
    python test_scalping_5ops.py              # Run with real IB Gateway
    python test_scalping_5ops.py --simulate   # Run simulation mode (no IB required)
"""
import asyncio
import configparser
import logging
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import csv

try:
    from ib_async import IB, Contract, MarketOrder, util
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

# Configure logging
log_file = Path(__file__).parent / 'test_scalping_5ops.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# Reduce verbosity from ib_async
if IB_AVAILABLE:
    util.logToConsole(logging.WARNING)


class SimulatedContract:
    """Simulated contract for testing without IB connection."""
    def __init__(self):
        self.symbol = 'EUR'
        self.localSymbol = 'EUR.USD'
        self.secType = 'CASH'
        self.exchange = 'IDEALPRO'
        self.currency = 'USD'


class SimulatedOrderStatus:
    """Simulated order status for testing."""
    def __init__(self, status='Filled', avg_fill_price=1.08500):
        self.status = status
        self.avgFillPrice = avg_fill_price


class SimulatedOrder:
    """Simulated order for testing."""
    def __init__(self, order_id):
        self.orderId = order_id


class SimulatedTrade:
    """Simulated trade for testing without IB connection."""
    _order_counter = 1000
    
    def __init__(self, action, quantity, base_price=1.08500):
        SimulatedTrade._order_counter += 1
        self.order = SimulatedOrder(SimulatedTrade._order_counter)
        # Simulate realistic price movement
        spread = random.uniform(-0.00005, 0.00005)
        slippage = random.uniform(0, 0.00002) * (1 if action == 'BUY' else -1)
        fill_price = base_price + spread + slippage
        self.orderStatus = SimulatedOrderStatus('Filled', fill_price)


class ScalpingTestRunner:
    """Executes a series of scalping test operations."""
    
    def __init__(self, host: str, port: int, client_id: int, simulate: bool = False):
        self.simulate = simulate
        self.ib = IB() if (IB_AVAILABLE and not simulate) else None
        self.host = host
        self.port = port
        self.client_id = client_id
        self.operations_log = []
        self.total_operations = 5
        self.quantity = 10000  # Default quantity for forex
        self._simulated_base_price = 1.08500  # Base EUR/USD price for simulation
        
    async def connect(self) -> bool:
        """Connect to IB Gateway with retry logic."""
        if self.simulate:
            logging.info("🔄 SIMULATION MODE - Skipping IB Gateway connection")
            return True
            
        if not IB_AVAILABLE:
            logging.error("❌ ib_async library not available. Install with: pip install ib_async")
            return False
            
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"Attempt {attempt}/{max_retries}: Connecting to {self.host}:{self.port}...")
                await self.ib.connectAsync(
                    self.host, 
                    self.port, 
                    clientId=self.client_id,
                    timeout=20
                )
                logging.info(f"✅ Connected to IB Gateway. Server version: {self.ib.client.serverVersion()}")
                return True
            except (ConnectionRefusedError, asyncio.TimeoutError) as e:
                logging.error(f"Connection attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    logging.info("Retrying in 5 seconds...")
                    await asyncio.sleep(5)
            except Exception as e:
                logging.critical(f"Unexpected connection error: {e}")
                return False
        logging.critical("❌ All connection attempts failed.")
        logging.info("💡 TIP: Make sure IB Gateway is running and SSH tunnel is active:")
        logging.info("   ssh -L 4002:127.0.0.1:4002 user@your-vps")
        return False
    
    def disconnect(self):
        """Disconnect from IB Gateway."""
        if self.simulate:
            logging.info("🔄 SIMULATION MODE - Skipping disconnect")
            return
        if self.ib and self.ib.isConnected():
            logging.info("Disconnecting from IB Gateway...")
            self.ib.disconnect()
            logging.info("✅ Disconnected.")
    
    async def setup_contract(self) -> Optional[Contract]:
        """Set up and qualify the trading contract (EUR/USD)."""
        if self.simulate:
            logging.info("🔄 SIMULATION MODE - Using simulated EUR/USD contract")
            return SimulatedContract()
            
        contract = Contract()
        contract.symbol = 'EUR'
        contract.secType = 'CASH'
        contract.exchange = 'IDEALPRO'
        contract.currency = 'USD'
        
        try:
            qualified = await self.ib.qualifyContractsAsync(contract)
            if qualified:
                logging.info(f"✅ Contract qualified: {contract.localSymbol}")
                return contract
            else:
                logging.error("❌ Failed to qualify contract.")
                return None
        except Exception as e:
            logging.error(f"❌ Error qualifying contract: {e}")
            return None
    
    async def warm_up_market_data(self, contract):
        """Warm up the market data connection for the contract."""
        if self.simulate:
            logging.info("🔄 SIMULATION MODE - Skipping market data warm-up")
            return
        logging.info("Warming up market data connection...")
        self.ib.reqMktData(contract, '', False, False)
        await asyncio.sleep(2)
        self.ib.cancelMktData(contract)
        logging.info("✅ Market data connection warmed up.")
    
    async def execute_scalping_operation(
        self, 
        operation_num: int, 
        contract
    ) -> dict:
        """
        Execute a single scalping operation (buy followed by sell).
        
        Returns:
            dict with operation details
        """
        result = {
            'operation_num': operation_num,
            'timestamp_start': datetime.now().isoformat(),
            'symbol': contract.localSymbol,
            'quantity': self.quantity,
            'buy_order_id': None,
            'buy_price': None,
            'buy_status': None,
            'sell_order_id': None,
            'sell_price': None,
            'sell_status': None,
            'pnl': None,
            'timestamp_end': None,
            'success': False,
            'error': None,
            'mode': 'SIMULATED' if self.simulate else 'LIVE'
        }
        
        logging.info(f"\n{'='*60}")
        logging.info(f"🚀 OPERATION {operation_num}/{self.total_operations} - Starting")
        logging.info(f"{'='*60}")
        
        try:
            if self.simulate:
                # SIMULATION MODE
                # Update base price with small random movement
                self._simulated_base_price += random.uniform(-0.0005, 0.0005)
                
                # Simulated BUY
                logging.info(f"📈 [SIM] Placing BUY order for {self.quantity} {contract.symbol}...")
                await asyncio.sleep(0.3)  # Simulate order placement delay
                buy_trade = SimulatedTrade('BUY', self.quantity, self._simulated_base_price)
                result['buy_order_id'] = buy_trade.order.orderId
                result['buy_status'] = buy_trade.orderStatus.status
                result['buy_price'] = buy_trade.orderStatus.avgFillPrice
                logging.info(f"✅ [SIM] BUY order filled at {result['buy_price']:.5f}")
                
                # Hold position
                logging.info("⏳ [SIM] Holding position for 1 second (scalping simulation)...")
                await asyncio.sleep(1)
                
                # Update price for sell (small movement)
                self._simulated_base_price += random.uniform(-0.0002, 0.0003)
                
                # Simulated SELL
                logging.info(f"📉 [SIM] Placing SELL order for {self.quantity} {contract.symbol}...")
                await asyncio.sleep(0.3)  # Simulate order placement delay
                sell_trade = SimulatedTrade('SELL', self.quantity, self._simulated_base_price)
                result['sell_order_id'] = sell_trade.order.orderId
                result['sell_status'] = sell_trade.orderStatus.status
                result['sell_price'] = sell_trade.orderStatus.avgFillPrice
                logging.info(f"✅ [SIM] SELL order filled at {result['sell_price']:.5f}")
            else:
                # LIVE MODE with IB Gateway
                # Step 1: Execute BUY order
                logging.info(f"📈 Placing BUY order for {self.quantity} {contract.symbol}...")
                buy_order = MarketOrder('BUY', self.quantity)
                buy_trade = self.ib.placeOrder(contract, buy_order)
                
                # Wait for the buy order to be filled
                start_wait = datetime.now()
                while buy_trade.orderStatus.status not in ['Filled', 'Cancelled', 'ApiCancelled']:
                    await asyncio.sleep(0.5)
                    if (datetime.now() - start_wait).seconds > 30:
                        logging.warning("⚠️ BUY order timeout - proceeding anyway")
                        break
                
                result['buy_order_id'] = buy_trade.order.orderId
                result['buy_status'] = buy_trade.orderStatus.status
                
                if buy_trade.orderStatus.status == 'Filled':
                    result['buy_price'] = buy_trade.orderStatus.avgFillPrice
                    logging.info(f"✅ BUY order filled at {result['buy_price']:.5f}")
                else:
                    logging.warning(f"⚠️ BUY order status: {buy_trade.orderStatus.status}")
                
                # Wait a moment for scalping simulation
                logging.info("⏳ Holding position for 2 seconds (scalping simulation)...")
                await asyncio.sleep(2)
                
                # Step 2: Execute SELL order to close the position
                logging.info(f"📉 Placing SELL order for {self.quantity} {contract.symbol}...")
                sell_order = MarketOrder('SELL', self.quantity)
                sell_trade = self.ib.placeOrder(contract, sell_order)
                
                # Wait for the sell order to be filled
                start_wait = datetime.now()
                while sell_trade.orderStatus.status not in ['Filled', 'Cancelled', 'ApiCancelled']:
                    await asyncio.sleep(0.5)
                    if (datetime.now() - start_wait).seconds > 30:
                        logging.warning("⚠️ SELL order timeout - proceeding anyway")
                        break
                
                result['sell_order_id'] = sell_trade.order.orderId
                result['sell_status'] = sell_trade.orderStatus.status
                
                if sell_trade.orderStatus.status == 'Filled':
                    result['sell_price'] = sell_trade.orderStatus.avgFillPrice
                    logging.info(f"✅ SELL order filled at {result['sell_price']:.5f}")
                else:
                    logging.warning(f"⚠️ SELL order status: {sell_trade.orderStatus.status}")
            
            # Calculate P&L if both orders filled
            if result['buy_price'] and result['sell_price']:
                pips = (result['sell_price'] - result['buy_price']) * 10000
                result['pnl'] = pips  # P&L in pips
                logging.info(f"📊 Operation P&L: {pips:.2f} pips")
                result['success'] = True
            
            result['timestamp_end'] = datetime.now().isoformat()
            logging.info(f"✅ Operation {operation_num} completed!")
            
        except Exception as e:
            result['error'] = str(e)
            result['timestamp_end'] = datetime.now().isoformat()
            logging.error(f"❌ Operation {operation_num} failed: {e}")
        
        return result
    
    async def run_test(self):
        """Run the complete test with 5 scalping operations."""
        mode_str = "SIMULATION" if self.simulate else "PAPER TRADING"
        logging.info("\n" + "="*70)
        logging.info(f"🎯 SCALPING TEST - 5 OPERATIONS ({mode_str})")
        logging.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info("="*70 + "\n")
        
        # Connect to IB Gateway
        if not await self.connect():
            return False
        
        try:
            # Setup contract
            contract = await self.setup_contract()
            if not contract:
                return False
            
            # Warm up market data
            await self.warm_up_market_data(contract)
            
            # Execute 5 scalping operations
            for i in range(1, self.total_operations + 1):
                result = await self.execute_scalping_operation(i, contract)
                self.operations_log.append(result)
                
                # Wait between operations (shorter in simulation)
                if i < self.total_operations:
                    wait_time = 1 if self.simulate else 3
                    logging.info(f"⏳ Waiting {wait_time} seconds before next operation...")
                    await asyncio.sleep(wait_time)
            
            # Generate summary
            self.print_summary()
            self.save_results_to_csv()
            
            return True
            
        except Exception as e:
            logging.error(f"❌ Test failed with error: {e}")
            return False
        finally:
            # Cancel any open orders (only for real connections)
            if not self.simulate and self.ib and self.ib.isConnected():
                self.ib.reqGlobalCancel()
                await asyncio.sleep(1)
            self.disconnect()
    
    def print_summary(self):
        """Print a summary of all operations."""
        mode_str = "SIMULATION" if self.simulate else "LIVE"
        logging.info("\n" + "="*70)
        logging.info(f"📋 SUMMARY OF SCALPING OPERATIONS ({mode_str})")
        logging.info("="*70)
        
        successful_ops = [op for op in self.operations_log if op['success']]
        failed_ops = [op for op in self.operations_log if not op['success']]
        
        total_pnl = sum(op['pnl'] for op in successful_ops if op['pnl'] is not None)
        
        logging.info(f"Mode: {mode_str}")
        logging.info(f"Total Operations: {len(self.operations_log)}")
        logging.info(f"Successful: {len(successful_ops)}")
        logging.info(f"Failed: {len(failed_ops)}")
        logging.info(f"Total P&L: {total_pnl:.2f} pips")
        
        logging.info("\n" + "-"*70)
        logging.info("DETAILED OPERATIONS:")
        logging.info("-"*70)
        
        for op in self.operations_log:
            status = "✅" if op['success'] else "❌"
            pnl_str = f"{op['pnl']:.2f} pips" if op['pnl'] else "N/A"
            buy_price = f"{op['buy_price']:.5f}" if op['buy_price'] else "N/A"
            sell_price = f"{op['sell_price']:.5f}" if op['sell_price'] else "N/A"
            
            logging.info(f"\n{status} Operation #{op['operation_num']}:")
            logging.info(f"   Symbol: {op['symbol']}")
            logging.info(f"   Quantity: {op['quantity']}")
            logging.info(f"   Buy Price: {buy_price} (Status: {op['buy_status']})")
            logging.info(f"   Sell Price: {sell_price} (Status: {op['sell_status']})")
            logging.info(f"   P&L: {pnl_str}")
            if op['error']:
                logging.info(f"   Error: {op['error']}")
        
        logging.info("\n" + "="*70)
        logging.info(f"Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info("="*70 + "\n")
    
    def save_results_to_csv(self):
        """Save operation results to a CSV file."""
        csv_file = Path(__file__).parent / 'test_scalping_5ops_results.csv'
        
        fieldnames = [
            'operation_num', 'timestamp_start', 'timestamp_end', 'symbol',
            'quantity', 'buy_order_id', 'buy_price', 'buy_status',
            'sell_order_id', 'sell_price', 'sell_status', 'pnl',
            'success', 'error', 'mode'
        ]
        
        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for op in self.operations_log:
                    writer.writerow(op)
            logging.info(f"📁 Results saved to: {csv_file}")
        except Exception as e:
            logging.error(f"❌ Failed to save CSV: {e}")


async def main(simulate: bool = False):
    """Main entry point."""
    # Load configuration
    config = configparser.ConfigParser()
    config_path = Path(__file__).parent / 'config.ini'
    
    if config_path.exists():
        config.read(config_path)
        ib_config = config['IB']
        host = ib_config.get('host', '127.0.0.1')
        port = ib_config.getint('port', 4002)
        client_id = ib_config.getint('client_id', 25)
    else:
        # Default configuration for paper trading
        host = '127.0.0.1'
        port = 4002
        client_id = 26  # Different client_id to avoid conflicts
        logging.warning(f"config.ini not found. Using defaults: {host}:{port}")
    
    mode_str = "SIMULATION" if simulate else "LIVE"
    logging.info(f"Mode: {mode_str}")
    logging.info(f"Configuration: host={host}, port={port}, client_id={client_id}")
    
    # Create and run test
    runner = ScalpingTestRunner(host, port, client_id, simulate=simulate)
    success = await runner.run_test()
    
    if success:
        logging.info("🎉 TEST COMPLETED SUCCESSFULLY!")
    else:
        logging.error("❌ TEST FAILED!")
    
    return success


if __name__ == "__main__":
    # Check for --simulate flag
    simulate_mode = '--simulate' in sys.argv or '-s' in sys.argv
    
    if simulate_mode:
        logging.info("="*70)
        logging.info("🔄 RUNNING IN SIMULATION MODE (no IB Gateway required)")
        logging.info("="*70)
    
    try:
        result = asyncio.run(main(simulate=simulate_mode))
        exit(0 if result else 1)
    except KeyboardInterrupt:
        logging.info("\n⚠️ Test interrupted by user (Ctrl+C)")
        exit(1)
    except Exception as e:
        logging.critical(f"❌ Critical error: {e}")
        exit(1)
