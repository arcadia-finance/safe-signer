This code is experimental and not audited.

To Build a Safe Transaction:
1) Complete the parameters in the file transaction_builder/script/utils/Constants.sol.
2) Create a new script inheriting from Base_Script (see transaction_builder/script/examples/*).
3) Run the script:
   - Go to the transaction_builder repository
   - Run "forge script <SCRIPT_NAME> --rpc-url <RPC_URL>"
4) The script will output the raw data of the transaction in the file "script/output.txt".

To generate the signatures for a Safe Transaction:
1) Complete the config file transaction_signer/config_transaction_signer.toml.
   - Complete the safes dict.
   - Complete the signers dict.
   - Complete the relayers (address broadcasting the transaction) dict.
   - Complete the raw data, obtained from the Safe Transaction Builder.
2) Create a .env file with:
   - HTTP_PROVIDER: An rpc-url for the chain the safe is deployed on.
   - KEY_NAME: If using hot wallets, A private key with the KEY_NAME as set in the config file.
   - If simulating transactions on Tenderly, set TENDERLY_KEY, TENDERLY_ACCOUNT and TENDERLY_PROJECT.
3) Run the script:
   - Go to the transaction_signer repository.
   - Run "poetry run python main.py".
   - Select the Safe.
   - Optionally, select: "Simulate transaction on Tenderly".
   - Select "Sign Message".
   - Select the Signer.
   - For the signers, the following devices are currently supported:
     - Trezor T (clear signing).
     - Trezor 1 (blind signing).
     - Ledger Nano S (sign domain and message hash).
     - Hot Wallet (blind signing).
4) The signature is saved in the file "transaction_signer/out/signatures.txt".
5) If multiple signatures are required:
   - Or Collect all signatures locally.
   - Or share the config_transaction_signer.toml and signatures.txt with the signers (can be done by forking this repo and share via git or any other means).
   - Repeat steps 3 and 4.

To broadcast the signed Safe Transaction:
1) The threshold of required number of signatures must be reached
2) Run the script:
   - Go to the transaction_signer repository.
   - Run "poetry run python main.py".
   - Select the Safe.
   - Optionally: Simulate transaction on Tenderly.
   - Select "Broadcast signed Safe tx".
   - Select the Relayer (can be any address, must not be one of signers).
   - For the relayers, the following devices are currently supported:
     - Trezor T (clear signing).
     - Hot Wallet (blind signing).
