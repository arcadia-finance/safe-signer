/**
 * Created by Pragma Labs
 * SPDX-License-Identifier: MIT
 */
pragma solidity ^0.8;

library Assets {
    // USDC on Base Sepolia.
    address internal constant USDC = 0xbf5bec5a2711719b5A2c344d17fBC276726ab1b1;
}

library Safes {
    // test Safe on Base Sepolia.
    address internal constant TEST = 0x1d2283161912aBC8dd9488037bCAcc42021d57D2;
}

library Spenders {
    address internal constant ALICE = address(1);
    address internal constant BOB = address(2);
}
