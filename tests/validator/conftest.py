import pytest

from eth_tester import EthereumTester
from eth_tester.backends.pyevm import PyEVMBackend
from viper import compiler
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider


GAS_PRICE = 25 * 10**9


def transaction_dict(from_addr, to_addr, gas, gas_price, value, data=""):
    return {
        "from": from_addr,
        "to": to_addr,
        "gas": gas,
        "gas_price": gas_price,
        "value": value,
        "data": data
    }


@pytest.fixture
def tester():
    return EthereumTester(backend=PyEVMBackend())


@pytest.fixture
def web3(tester):
    return Web3(EthereumTesterProvider(tester))


@pytest.fixture
def gas_limit(web3):
    return web3.eth.getBlock('latest')['gasLimit']


@pytest.fixture
def casper_chain(
        web3,
        tester,
        gas_limit,
        casper_args,
        casper_code,
        casper_abi,
        casper_ct,
        dependency_transactions,
        dependency_raw_transactions,
        sig_hasher_address,
        purity_checker_address):
    # Create transactions for instantiating RLP decoder, sig hasher and purity checker,
    # plus transactions for feeding the one-time accounts that generate those transactions
    funding_transactions = []
    for tx in dependency_transactions:
        funding_transactions.append({
            "to": web3.toChecksumAddress(web3.toHex(tx.sender)),
            "gas": 21000,
            "gas_price": GAS_PRICE,
            "value": tx.startgas * tx.gasprice + tx.value
        })

    gas_used = 0
    for tx in funding_transactions:
        if gas_used + tx["gas"] > gas_limit:
            web3.testing.mine()
            gas_used = 0
        web3.eth.sendTransaction(tx)

    for tx, raw_tx in zip(dependency_transactions, dependency_raw_transactions):
        if gas_used + tx.startgas > gas_limit:
            web3.testing.mine()
            gas_used = 0
        gas_used += tx.startgas
        web3.eth.sendRawTransaction(raw_tx)

    web3.testing.mine()

    # NOTE: bytecode cannot be compiled before RLP Decoder is deployed to chain
    # otherwise, viper compiler cannot properly embed RLP decoder address
    casper_bytecode = compiler.compile(casper_code)
    contract = web3.eth.contract(abi=casper_abi, bytecode=casper_bytecode)
    print(casper_abi)
    tx_hash = contract.deploy(
        transaction={'gas': 5000000, 'gas_price': GAS_PRICE},
        args=casper_args
    )
    tx_receipt = web3.eth.getTransactionReceipt(tx_hash)
    contract_address = tx_receipt['contractAddress']

    return casper_chain


