import os
import time
import math
import bip39
import breez_sdk
import cmd
from secrets_loader import load_secrets
from breez_sdk import LnUrlCallbackStatus, LnUrlPayResult, PaymentTypeFilter
from info_printer import InfoPrinter

# SDK events listener
class SDKListener(breez_sdk.EventListener):
   def on_event(self, event):
      pass

class Wallet(cmd.Cmd, InfoPrinter):
  def __init__(self):
    super().__init__()

    # Load secrets from file
    secrets = load_secrets('secrets.txt')

    # Create the default config
    mnemonic = secrets['phrase']
    invite_code = secrets['invite_code']
    api_key = secrets['api_key']
    seed = bip39.phrase_to_seed(mnemonic)

    config = breez_sdk.default_config(breez_sdk.EnvironmentType.PRODUCTION, api_key,
        breez_sdk.NodeConfig.GREENLIGHT(breez_sdk.GreenlightNodeConfig(None, invite_code)))

    # Customize the config object according to your needs
    config.working_dir = os.getcwd()

    # Connect to the Breez SDK make it ready for use
    self.sdk_services = breez_sdk.connect(config, seed, SDKListener())
    self.prompt = 'wallet> '

  def do_info(self, arg):
    """Get node info"""
    try:
      node_info = self.sdk_services.node_info()
      lsp_id = self.sdk_services.lsp_id()
      lsp_info = self.sdk_services.fetch_lsp_info(lsp_id)
      self._print_node_info(node_info)
      self._print_lsp_info(lsp_info)
    except Exception as error:
      print('Error getting LSP info: ', error)

  def do_get_balance(self, arg):
    """Get balance"""
    # Logic to get balance
    node_info = self.sdk_services.node_info()
    ln_balance = node_info.channels_balance_msat
    onchain_balance = node_info.onchain_balance_msat
    print('Lightning balance: ', ln_balance, ' millisatoshis, On-chain balance: ', onchain_balance, ' millisatoshis')

  def do_get_deposit_address(self, arg):
    """Get deposit address (on-chain)"""
    # Logic to get deposit address (on-chain)
    swap_info = self.sdk_services.receive_onchain()
    self._print_swap_info(swap_info)

  def do_swap_progress(self, arg):
    """Get the progress of any in-progress swap"""
    try:
      swap_info = self.sdk_services.in_progress_swap()
      if swap_info:
        self._print_swap_info(swap_info)
      else:
        print('No in-progress swap')
    except Exception as error:
      print('Error getting swap progress: ', error)

  def do_list_refundables(self, arg):
    """List of refundable operations"""
    try:
      refundables = self.sdk_services.list_refundables()
      print(refundables)
    except Exception as error:
      print('Error getting refundables: ', error)

  def do_send_funds(self, arg):
    """Send funds (on-chain)
    """
    # Logic to send funds (on-chain)
    pass

  def do_get_lightning_invoice(self, arg):
    """Get lightning invoice (off-chain)"""
    [amount, memo] = arg.split(' ')
    print(f'Getting invoice for amount: {amount}')
    if memo:
        print(f'With memo: {memo}')
    try:
      invoice = self.sdk_services.receive_payment(amount, f'Invoice for {amount} sats')
      print('pay: ', invoice.bolt11)
    except Exception as error:
      # Handle error
      print('error getting invoice: ', error)

  def do_pay_invoice(self, args):
    """Pay lightning invoice (off-chain)
    Usage: pay_invoice <invoice>
    """
    invoice = args.strip()
    print('\nPaying invoice.....: ', invoice)
    try:
      self.sdk_services.send_payment(invoice, None)
      print('✅ Payment success!')
    except Exception as error:
      # Handle error
      print('error paying invoice: ', error)

  def do_lnurl_withdraw(self, args):
    """Withdraw using LNURL-withdraw (off-chain)
    Usage: lnurl_withdraw <lnurl> <amount>
    """
    if len(args.split(' ')) != 2:
      print('Usage: lnurl_withdraw <lnurl> <amount>')
      return
    [lnurl, amount] = args.split(' ')[:2]
    print('\n=== Withdrawing using LNURL-withdraw ===')
    print(f'LNURL: {lnurl}')
    print('========================================')
    try:
      parsed_input = breez_sdk.parse_input(lnurl)
      if isinstance(parsed_input, breez_sdk.InputType.LN_URL_WITHDRAW):
        self.print_ln_url_withdraw_request_data(parsed_input.data)
        minimum = parsed_input.data.min_withdrawable
        maximum = parsed_input.data.max_withdrawable
        if amount is None:
          print(f'Please chose an amount in the range [{minimum} - {maximum}] msats')
          return
        amount_sats = int(amount)
        amount_msats = int(amount) * 1E3
        if amount_msats < minimum:
          print('Amount is less than minimum')
          return
        if amount_msats > maximum:
          print('Amount is greater than maximum')
          return
        print(f'⏳ *** Requesting a withdrawal of {amount_sats} sats ***')
        result = self.sdk_services.withdraw_lnurl(parsed_input.data, amount_sats, "withdrawing using lnurl")
        if isinstance(result, LnUrlCallbackStatus.OK):
          print(f'🎉 You successfully withdrew {amount_sats} sats!')
        elif isinstance(result, LnUrlCallbackStatus.ERROR):
          print('😔 Withdraw error: ', result)
      else:
        print('Invalid lnurl')
    except Exception as error:
      print('❌ Error withdrawing using lnurl: ', error)

  def do_lnurl_pay(self, args):
    """Pay using LNURL-pay (off-chain)
    Usage: lnurl_pay <url|ln_address> <amount> [memo]
    """
    [url, amount] = args.split(' ')[:2]
    memo = ' '.join(args.split(' ')[2:])
    print('\n=== Paying using LNURL-pay ===')
    print(f'URL.....: {url}')
    print(f'Amount..: {amount}')
    print(f'Memo....: {memo}')
    print('==============================')
    try:
      parsed_input = breez_sdk.parse_input(url)
      if isinstance(parsed_input, breez_sdk.InputType.LN_URL_PAY):
        min_sendable = parsed_input.data.min_sendable
        max_sendable = parsed_input.data.max_sendable
        sats_amount = int(amount)
        if sats_amount > max_sendable or sats_amount < min_sendable:
          print(f'Amount is out of range, make sure it is between {min_sendable} and {max_sendable}')
          return
        result = self.sdk_services.pay_lnurl(parsed_input.data, sats_amount, memo)
        if isinstance(result, LnUrlPayResult.ENDPOINT_SUCCESS):
          print('🎉 Payment successful!')
        elif isinstance(result, LnUrlPayResult.ENDPOINT_ERROR):
          print('😢 Payment failed!')
        else:
          print('Unknown result: ', result)
    except Exception as error:
      print('error paying lnurl-pay: ', error)

  def do_send(self, args):
    """Makes a spontaneous payment (off-chain) to a node
    Usage: send <node_id> <amount>
    """
    [node_id, _amount] = args.split(' ')
    amount = math.floor(float(_amount))
    try:
      self.sdk_services.send_spontaneous_payment(node_id, amount)
    except Exception as error:
      print('error sending payment: ', error)

  def do_txs(self, arg):
    """List transactions"""
    # Logic to list payments
    now = time.time()
    payments = self.sdk_services.list_payments(PaymentTypeFilter.ALL, 0, now)
    self._print_payments(payments)

  def do_exit(self, arg):
      """Exit the application."""
      print("Goodbye!")
      return True

if __name__ == '__main__':
  cli = Wallet()
  cli.cmdloop('Welcome to the Breez SDK Wallet!\n\nType `help` or `?` to list commands.')