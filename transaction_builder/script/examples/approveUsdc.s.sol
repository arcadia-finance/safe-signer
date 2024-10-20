/**
 * Created by Pragma Labs
 * SPDX-License-Identifier: MIT
 */
pragma solidity ^0.8;

import { Assets, Safes, Spenders } from "../utils/Constants.sol";
import { Base_Script } from "../Base.s.sol";

interface IERC20 {
    function approve(address spender, uint256 amount) external returns (bool);
}

contract ApproveUsdc is Base_Script {
    IERC20 internal constant USDC = IERC20(Assets.USDC);

    constructor() { }

    function run() public {
        // Approve Alice.
        bytes memory calldata_ = abi.encodeCall(USDC.approve, (Spenders.ALICE, type(uint256).max));
        addToBatch(Safes.TEST, Assets.USDC, calldata_);

        // Approve Bob.
        calldata_ = abi.encodeCall(USDC.approve, (Spenders.BOB, type(uint256).max));
        addToBatch(Safes.TEST, Assets.USDC, calldata_);

        // Create and write away batched transaction data to be signed with Safe.
        bytes memory data = createBatchedData(Safes.TEST);
        vm.writeLine(PATH, vm.toString(data));
    }
}
