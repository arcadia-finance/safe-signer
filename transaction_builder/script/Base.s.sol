/**
 * Created by Pragma Labs
 * SPDX-License-Identifier: MIT
 */
pragma solidity ^0.8;

import { SafeTransactionBuilder } from "./utils/SafeTransactionBuilder.sol";
import { Test } from "../lib/forge-std/src/Test.sol";

abstract contract Base_Script is Test, SafeTransactionBuilder {
    constructor() { }
}
