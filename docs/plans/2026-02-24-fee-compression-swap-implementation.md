# Fee Compression Swap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a Fee Compression Swap (FCS) derivative protocol that allows LPs to hedge against fee revenue dilution from LP competition, using ERC6909 tokenization and a CFMM with custom payoff functions.

**Architecture:** Build a modular Solidity protocol with (1) oracle integration for feeGrowth data from Uniswap V3, (2) variance calculation engine, (3) perpetual CFMM with custom payoff function, (4) ERC6909 vault for position tokenization, and (5) extensible payoff function registry supporting linear, log, and digital payoffs.

**Tech Stack:** Solidity 0.8.x, Foundry for testing, ERC6909 for tokenization, Chainlink Functions or custom oracle for feeGrowth data, Uniswap V3 subgraph for historical calibration.

**Key Design Decisions:**
- **Payoff:** Linear variance swap (MVP), extensible to log and digital
- **Replication:** Oracle-settled CFMM with static range accrual portfolio backing
- **Settlement:** Perpetual funding model with CFMM structure
- **Tokenization:** ERC6909 for multi-position efficiency
- **Pricing:** Model-agnostic initially (calibration phase separate)

---

## Phase 1: Oracle & Data Infrastructure

### Task 1: Define FeeGrowth Oracle Interface

**Files:**
- Create: `src/interfaces/IFeeGrowthOracle.sol`
- Create: `src/types/FeeGrowthData.sol`
- Test: `test/oracle/IFeeGrowthOracle.t.sol`

**Step 1: Write the failing test**

```solidity
// test/oracle/IFeeGrowthOracle.t.sol

// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

import "forge-std/Test.sol";
import "../src/interfaces/IFeeGrowthOracle.sol";
import "../src/types/FeeGrowthData.sol";

contract FeeGrowthOracleTest is Test {
    IFeeGrowthOracle public oracle;
    
    function setUp() public {
        // Deploy mock oracle
        oracle = new MockFeeGrowthOracle();
    }
    
    function test_getFeeGrowthOutside_returnsStruct() public {
        FeeGrowthData.FeeGrowth memory data = oracle.getFeeGrowthOutside(
            address(0x123),
            -887220,
            887220
        );
        
        assertEq(data.tickLower, -887220);
        assertEq(data.tickUpper, 887220);
        // Additional assertions on feeGrowth values
    }
    
    function test_getFeeGrowthInside_returnsStruct() public {
        FeeGrowthData.FeeGrowthInside memory data = oracle.getFeeGrowthInside(
            address(0x123),
            bytes32(0xabc)
        );
        
        assertGt(data.feeGrowthInside0X128, 0);
        assertGt(data.feeGrowthInside1X128, 0);
    }
    
    function test_getMonopolisticFeeGrowth_calculatesCorrectly() public {
        uint256 monoFeeGrowth = oracle.getMonopolisticFeeGrowth(
            address(0x123),
            -887220,
            887220
        );
        
        // Should be weighted average of feeGrowthOutside at boundaries
        assertGt(monoFeeGrowth, 0);
    }
    
    function test_calculateVariance_acrossPositions() public {
        bytes32[] memory positionIds = new bytes32[](3);
        positionIds[0] = bytes32(0x1);
        positionIds[1] = bytes32(0x2);
        positionIds[2] = bytes32(0x3);
        
        uint256 variance = oracle.calculateVariance(
            address(0x123),
            -887220,
            887220,
            positionIds
        );
        
        assertGt(variance, 0);
    }
}
```

**Step 2: Run test to verify it fails**

```bash
forge test --match-test test_getFeeGrowthOutside_returnsStruct -vvv
# Expected: FAIL with "unresolved symbol" or "contract not found"
```

**Step 3: Write minimal implementation**

```solidity
// src/types/FeeGrowthData.sol

// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

/// @title FeeGrowthData
/// @notice Data structures for fee growth tracking
library FeeGrowthData {
    /// @notice Fee growth data for a tick range
    struct FeeGrowth {
        int24 tickLower;
        int24 tickUpper;
        uint256 feeGrowthOutside0X128;
        uint256 feeGrowthOutside1X128;
        uint256 sqrtPriceX96;
    }
    
    /// @notice Fee growth inside a specific position
    struct FeeGrowthInside {
        bytes32 positionId;
        uint256 feeGrowthInside0X128;
        uint256 feeGrowthInside1X128;
        uint128 liquidity;
    }
    
    /// @notice Variance calculation result
    struct VarianceResult {
        uint256 variance;
        uint256 mean;
        uint256 nPositions;
        uint256 timestamp;
    }
    
    /// @notice Convert feeGrowthOutside to numeraire dimension
    /// @param feeGrowthOutside0X128 Fee growth outside in Q128 format
    /// @param feeGrowthOutside1X128 Fee growth outside in Q128 format
    /// @param sqrtPriceX96 Square root of price in Q96 format
    /// @return Fee growth in numeraire terms
    function toNumeraire(
        uint256 feeGrowthOutside0X128,
        uint256 feeGrowthOutside1X128,
        uint256 sqrtPriceX96
    ) internal pure returns (uint256) {
        // $monopolisticFeeGrowth = sqrtPriceX96 * feeGrowthOutside0x128 + feeGrowthOutside1x128
        // Note: Requires proper Q96/Q128 fixed point arithmetic
        uint256 term1 = (sqrtPriceX96 * feeGrowthOutside0X128) / (1 << 96);
        return term1 + feeGrowthOutside1X128;
    }
    
    /// @notice Calculate variance from array of values
    /// @param values Array of fee growth ratios
    /// @return Variance of the values
    function calculateVariance(uint256[] memory values) 
        internal 
        pure 
        returns (uint256) 
    {
        uint256 n = values.length;
        require(n > 0, "FeeGrowthData: empty array");
        
        // Calculate mean
        uint256 sum = 0;
        for (uint256 i = 0; i < n; i++) {
            sum += values[i];
        }
        uint256 mean = sum / n;
        
        // Calculate variance
        uint256 varianceSum = 0;
        for (uint256 i = 0; i < n; i++) {
            int256 diff = int256(values[i]) - int256(mean);
            varianceSum += uint256(diff * diff);
        }
        
        return varianceSum / n;
    }
}
```

```solidity
// src/interfaces/IFeeGrowthOracle.sol

// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

import "../types/FeeGrowthData.sol";

/// @title IFeeGrowthOracle
/// @notice Interface for fee growth data oracle
interface IFeeGrowthOracle {
    /// @notice Get fee growth outside for a tick range
    /// @param pool Uniswap V3 pool address
    /// @param tickLower Lower tick
    /// @param tickUpper Upper tick
    /// @return Fee growth data struct
    function getFeeGrowthOutside(
        address pool,
        int24 tickLower,
        int24 tickUpper
    ) external view returns (FeeGrowthData.FeeGrowth memory);
    
    /// @notice Get fee growth inside for a position
    /// @param pool Uniswap V3 pool address
    /// @param positionId Position ID (keccak256 of owner, tickLower, tickUpper)
    /// @return Fee growth inside struct
    function getFeeGrowthInside(
        address pool,
        bytes32 positionId
    ) external view returns (FeeGrowthData.FeeGrowthInside memory);
    
    /// @notice Calculate monopolistic fee growth for a tick range
    /// @dev Weighted average of feeGrowthOutside at boundaries
    /// @param pool Uniswap V3 pool address
    /// @param tickLower Lower tick
    /// @param tickUpper Upper tick
    /// @return Monopolistic fee growth in numeraire terms
    function getMonopolisticFeeGrowth(
        address pool,
        int24 tickLower,
        int24 tickUpper
    ) external view returns (uint256);
    
    /// @notice Calculate variance of fee compression across positions
    /// @param pool Uniswap V3 pool address
    /// @param tickLower Lower tick
    /// @param tickUpper Upper tick
    /// @param positionIds Array of position IDs in the range
    /// @return Variance calculation result
    function calculateVariance(
        address pool,
        int24 tickLower,
        int24 tickUpper,
        bytes32[] calldata positionIds
    ) external view returns (FeeGrowthData.VarianceResult memory);
}
```

**Step 4: Run test to verify it passes**

```bash
forge test --match-test test_getFeeGrowthOutside_returnsStruct -vvv
# Expected: PASS
```

**Step 5: Commit**

```bash
git add src/interfaces/IFeeGrowthOracle.sol src/types/FeeGrowthData.sol test/oracle/IFeeGrowthOracle.t.sol
git commit -m "feat: define fee growth oracle interface and data types"
```

---

### Task 2: Implement Uniswap V3 FeeGrowth Oracle

**Files:**
- Create: `src/oracle/UniswapV3FeeGrowthOracle.sol`
- Create: `src/libraries/UniswapV3Library.sol`
- Test: `test/oracle/UniswapV3FeeGrowthOracle.t.sol`

**Step 1: Write the failing test**

```solidity
// test/oracle/UniswapV3FeeGrowthOracle.t.sol

// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

import "forge-std/Test.sol";
import "../src/oracle/UniswapV3FeeGrowthOracle.sol";
import "../src/interfaces/IUniswapV3Pool.sol";

contract UniswapV3FeeGrowthOracleTest is Test {
    UniswapV3FeeGrowthOracle public oracle;
    
    // Mainnet ETH/USDC 0.05% pool
    address constant ETH_USDC_POOL = 0x88e6A0c2dDD26FEEb64f039a2c41296FcB3f5640;
    
    function setUp() public {
        oracle = new UniswapV3FeeGrowthOracle();
    }
    
    function test_getFeeGrowthOutside_readsFromPool() public {
        // Fork mainnet for integration test
        vm.createSelectFork(vm.envString("MAINNET_RPC_URL"));
        
        FeeGrowthData.FeeGrowth memory data = oracle.getFeeGrowthOutside(
            ETH_USDC_POOL,
            -887220,
            887220
        );
        
        assertEq(data.tickLower, -887220);
        assertEq(data.tickUpper, 887220);
        assertGt(data.feeGrowthOutside0X128, 0);
        assertGt(data.feeGrowthOutside1X128, 0);
    }
    
    function test_getMonopolisticFeeGrowth_weightedAverage() public {
        vm.createSelectFork(vm.envString("MAINNET_RPC_URL"));
        
        uint256 monoFeeGrowth = oracle.getMonopolisticFeeGrowth(
            ETH_USDC_POOL,
            -2000,
            2000
        );
        
        // Should be between the two boundary values
        FeeGrowthData.FeeGrowth memory data = oracle.getFeeGrowthOutside(
            ETH_USDC_POOL,
            -2000,
            2000
        );
        
        assertGt(monoFeeGrowth, 0);
    }
    
    function test_calculateVariance_multiplePositions() public {
        vm.createSelectFork(vm.envString("MAINNET_RPC_URL"));
        
        bytes32[] memory positionIds = new bytes32[](2);
        positionIds[0] = bytes32(0x1);
        positionIds[1] = bytes32(0x2);
        
        FeeGrowthData.VarianceResult memory result = oracle.calculateVariance(
            ETH_USDC_POOL,
            -2000,
            2000,
            positionIds
        );
        
        assertGt(result.nPositions, 0);
        assertGt(result.variance, 0);
        assertEq(result.timestamp, block.timestamp);
    }
}
```

**Step 2: Run test to verify it fails**

```bash
forge test --match-test test_getFeeGrowthOutside_readsFromPool -vvv
# Expected: FAIL (contract doesn't exist yet)
```

**Step 3: Write minimal implementation**

```solidity
// src/libraries/UniswapV3Library.sol

// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

/// @title UniswapV3Library
/// @notice Helper functions for Uniswap V3 interaction
library UniswapV3Library {
    /// @notice Compute position ID from owner and tick range
    /// @param owner Position owner
    /// @param tickLower Lower tick
    /// @param tickUpper Upper tick
    /// @return Position ID (bytes32)
    function getPositionId(
        address owner,
        int24 tickLower,
        int24 tickUpper
    ) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(owner, tickLower, tickUpper));
    }
    
    /// @notice Get pool tick spacing
    /// @param pool Uniswap V3 pool address
    /// @return Tick spacing
    function getTickSpacing(address pool) 
        internal 
        view 
        returns (int24) 
    {
        // Call pool.tickSpacing()
        (, , , , , , int24 tickSpacing) = IUniswapV3Pool(pool).slot0();
        return tickSpacing;
    }
    
    /// @notice Convert Q128 fixed point to uint256
    /// @param valueQ128 Value in Q128 format
    /// @return Value as uint256 (scaled)
    function fromQ128(uint256 valueQ128) 
        internal 
        pure 
        returns (uint256) 
    {
        return valueQ128 >> 128;
    }
    
    /// @notice Convert Q96 fixed point to uint256
    /// @param valueQ96 Value in Q96 format
    /// @return Value as uint256 (scaled)
    function fromQ96(uint256 valueQ96) 
        internal 
        pure 
        returns (uint256) 
    {
        return valueQ96 >> 96;
    }
}

/// @title IUniswapV3Pool
/// @notice Minimal interface for Uniswap V3 pool
interface IUniswapV3Pool {
    function slot0() 
        external 
        view 
        returns (
            uint160 sqrtPriceX96,
            int24 tick,
            uint16 observationIndex,
            uint16 observationCardinality,
            uint16 observationCardinalityNext,
            uint8 feeProtocol,
            bool unlocked
        );
    
    function tickBitmap(int16 wordPosition) 
        external 
        view 
        returns (uint256);
    
    function positions(bytes32 key) 
        external 
        view 
        returns (
            uint128 liquidity,
            uint256 feeGrowthInside0LastX128,
            uint256 feeGrowthInside1LastX128,
            uint128 tokensOwed0,
            uint128 tokensOwed1
        );
    
    function ticks(int24 tick) 
        external 
        view 
        returns (
            uint128 liquidityGross,
            int128 liquidityNet,
            uint256 feeGrowthOutside0X128,
            uint256 feeGrowthOutside1X128,
            int56 tickCumulativeOutside,
            uint160 secondsPerLiquidityOutsideX128,
            uint32 secondsOutside,
            bool initialized
        );
}
```

```solidity
// src/oracle/UniswapV3FeeGrowthOracle.sol

// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

import "../interfaces/IFeeGrowthOracle.sol";
import "../types/FeeGrowthData.sol";
import "../libraries/UniswapV3Library.sol";

/// @title UniswapV3FeeGrowthOracle
/// @notice Oracle for reading fee growth data from Uniswap V3
contract UniswapV3FeeGrowthOracle is IFeeGrowthOracle {
    using FeeGrowthData for *;
    using UniswapV3Library for *;
    
    /// @notice Get fee growth outside for a tick range
    function getFeeGrowthOutside(
        address pool,
        int24 tickLower,
        int24 tickUpper
    ) external view override returns (FeeGrowthData.FeeGrowth memory) {
        IUniswapV3Pool poolContract = IUniswapV3Pool(pool);
        
        // Read tick data
        (, , uint256 feeGrowthOutside0X128_lower, uint256 feeGrowthOutside1X128_lower, , , , ) 
            = poolContract.ticks(tickLower);
        
        (, , uint256 feeGrowthOutside0X128_upper, uint256 feeGrowthOutside1X128_upper, , , , ) 
            = poolContract.ticks(tickUpper);
        
        // Get current price
        (uint256 sqrtPriceX96, , , , , , ) = poolContract.slot0();
        
        // For monopolistic calculation, we use the boundary values
        // Weighted average would require more complex calculation
        // For MVP, use simple average
        uint256 avgFeeGrowthOutside0 = (feeGrowthOutside0X128_lower + feeGrowthOutside0X128_upper) / 2;
        uint256 avgFeeGrowthOutside1 = (feeGrowthOutside1X128_lower + feeGrowthOutside1X128_upper) / 2;
        
        return FeeGrowthData.FeeGrowth({
            tickLower: tickLower,
            tickUpper: tickUpper,
            feeGrowthOutside0X128: avgFeeGrowthOutside0,
            feeGrowthOutside1X128: avgFeeGrowthOutside1,
            sqrtPriceX96: sqrtPriceX96
        });
    }
    
    /// @notice Get fee growth inside for a position
    function getFeeGrowthInside(
        address pool,
        bytes32 positionId
    ) external view override returns (FeeGrowthData.FeeGrowthInside memory) {
        IUniswapV3Pool poolContract = IUniswapV3Pool(pool);
        
        // Read position data
        (
            uint128 liquidity,
            uint256 feeGrowthInside0LastX128,
            uint256 feeGrowthInside1LastX128,
            ,
            
        ) = poolContract.positions(positionId);
        
        return FeeGrowthData.FeeGrowthInside({
            positionId: positionId,
            feeGrowthInside0X128: feeGrowthInside0LastX128,
            feeGrowthInside1X128: feeGrowthInside1LastX128,
            liquidity: liquidity
        });
    }
    
    /// @notice Calculate monopolistic fee growth
    function getMonopolisticFeeGrowth(
        address pool,
        int24 tickLower,
        int24 tickUpper
    ) external view override returns (uint256) {
        FeeGrowthData.FeeGrowth memory data = this.getFeeGrowthOutside(
            pool,
            tickLower,
            tickUpper
        );
        
        // Convert to numeraire dimension
        return FeeGrowthData.toNumeraire(
            data.feeGrowthOutside0X128,
            data.feeGrowthOutside1X128,
            data.sqrtPriceX96
        );
    }
    
    /// @notice Calculate variance across positions
    function calculateVariance(
        address pool,
        int24 tickLower,
        int24 tickUpper,
        bytes32[] calldata positionIds
    ) external view override returns (FeeGrowthData.VarianceResult memory) {
        uint256 n = positionIds.length;
        require(n > 0, "UniswapV3FeeGrowthOracle: no positions");
        
        // Get monopolistic fee growth (common numerator)
        uint256 monoFeeGrowth = this.getMonopolisticFeeGrowth(
            pool,
            tickLower,
            tickUpper
        );
        
        // Calculate fee compression ratio for each position
        uint256[] memory ratios = new uint256[](n);
        uint256 sum = 0;
        
        for (uint256 i = 0; i < n; i++) {
            FeeGrowthData.FeeGrowthInside memory posData = this.getFeeGrowthInside(
                pool,
                positionIds[i]
            );
            
            // Calculate position's fee growth in numeraire
            uint256 posFeeGrowth = FeeGrowthData.toNumeraire(
                posData.feeGrowthInside0X128,
                posData.feeGrowthInside1X128,
                monoFeeGrowth // Use as proxy for sqrtPriceX96
            );
            
            // Ratio: monopolistic / competitive
            // If posFeeGrowth is 0, ratio is max (division by zero protection)
            if (posFeeGrowth > 0) {
                ratios[i] = (monoFeeGrowth * 1e18) / posFeeGrowth;
            } else {
                ratios[i] = type(uint256).max;
            }
            
            sum += ratios[i];
        }
        
        // Calculate mean
        uint256 mean = sum / n;
        
        // Calculate variance
        uint256 variance = FeeGrowthData.calculateVariance(ratios);
        
        return FeeGrowthData.VarianceResult({
            variance: variance,
            mean: mean,
            nPositions: n,
            timestamp: block.timestamp
        });
    }
}
```

**Step 4: Run test to verify it passes**

```bash
forge test --match-test test_getFeeGrowthOutside_readsFromPool -vvv
# Expected: PASS (requires mainnet fork)
```

**Step 5: Commit**

```bash
git add src/oracle/UniswapV3FeeGrowthOracle.sol src/libraries/UniswapV3Library.sol test/oracle/UniswapV3FeeGrowthOracle.t.sol
git commit -m "feat: implement Uniswap V3 fee growth oracle"
```

---

## Phase 2: Payoff Function Registry

### Task 3: Define Payoff Function Interface

**Files:**
- Create: `src/interfaces/IPayoffFunction.sol`
- Create: `src/types/PayoffData.sol`
- Test: `test/payoff/IPayoffFunction.t.sol`

**Step 1: Write the failing test**

```solidity
// test/payoff/IPayoffFunction.t.sol

// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

import "forge-std/Test.sol";
import "../src/interfaces/IPayoffFunction.sol";
import "../src/types/PayoffData.sol";

contract PayoffFunctionTest is Test {
    function test_linearPayoff_calculatesCorrectly() public {
        PayoffData.PayoffParams memory params = PayoffData.PayoffParams({
            notional: 100_000e18,  // $100,000
            strikeVariance: 0.01e18,  // 1% variance
            realizedVariance: 0.015e18,  // 1.5% variance
            payoffType: PayoffData.PayoffType.LINEAR
        });
        
        uint256 payoff = PayoffFunctions.calculatePayoff(params);
        
        // Expected: 100,000 * (0.015 - 0.01) = 500
        assertEq(payoff, 500e18);
    }
    
    function test_logPayoff_calculatesCorrectly() public {
        PayoffData.PayoffParams memory params = PayoffData.PayoffParams({
            notional: 100_000e18,
            strikeVariance: 0.01e18,
            realizedVariance: 0.015e18,
            payoffType: PayoffData.PayoffType.LOG
        });
        
        uint256 payoff = PayoffFunctions.calculatePayoff(params);
        
        // Expected: 100,000 * (ln(0.015) - ln(0.01)) = 100,000 * 0.405 = 40,500
        // Approximate check
        assertGt(payoff, 40_000e18);
        assertLt(payoff, 41_000e18);
    }
    
    function test_digitalPayoff_calculatesCorrectly() public {
        PayoffData.PayoffParams memory params = PayoffData.PayoffParams({
            notional: 100_000e18,
            strikeVariance: 0.01e18,
            realizedVariance: 0.015e18,
            payoffType: PayoffData.PayoffType.DIGITAL
        });
        
        uint256 payoff = PayoffFunctions.calculatePayoff(params);
        
        // Digital pays full notional if realized > strike
        assertEq(payoff, 100_000e18);
    }
    
    function test_digitalPayoff_outOfMoney() public {
        PayoffData.PayoffParams memory params = PayoffData.PayoffParams({
            notional: 100_000e18,
            strikeVariance: 0.01e18,
            realizedVariance: 0.008e18,  // Below strike
            payoffType: PayoffData.PayoffType.DIGITAL
        });
        
        uint256 payoff = PayoffFunctions.calculatePayoff(params);
        
        // Digital pays nothing if realized < strike
        assertEq(payoff, 0);
    }
}
```

**Step 2: Run test to verify it fails**

```bash
forge test --match-test test_linearPayoff_calculatesCorrectly -vvv
# Expected: FAIL
```

**Step 3: Write minimal implementation**

```solidity
// src/types/PayoffData.sol

// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

/// @title PayoffData
/// @notice Data structures for Fee Compression Swap payoffs
library PayoffData {
    /// @notice Type of payoff function
    enum PayoffType {
        LINEAR,    // Payoff = notional × (realized - strike)
        LOG,       // Payoff = notional × (ln(realized) - ln(strike))
        DIGITAL    // Payoff = notional if realized > strike, else 0
    }
    
    /// @notice Parameters for payoff calculation
    struct PayoffParams {
        uint256 notional;
        uint256 strikeVariance;
        uint256 realizedVariance;
        PayoffType payoffType;
    }
    
    /// @notice Payoff calculation result
    struct PayoffResult {
        uint256 amount;
        PayoffType payoffType;
        bool isPositive;
    }
}
```

```solidity
// src/interfaces/IPayoffFunction.sol

// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

import "../types/PayoffData.sol";

/// @title IPayoffFunction
/// @notice Interface for payoff function calculations
interface IPayoffFunction {
    /// @notice Calculate payoff for given parameters
    /// @param params Payoff calculation parameters
    /// @return Payoff amount (in same units as notional)
    function calculatePayoff(
        PayoffData.PayoffParams calldata params
    ) external pure returns (uint256);
    
    /// @notice Get supported payoff types
    /// @return Array of supported payoff types
    function getSupportedPayoffTypes() 
        external 
        pure 
        returns (PayoffData.PayoffType[] memory);
}
```

```solidity
// src/payoff/PayoffFunctions.sol

// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

import "../interfaces/IPayoffFunction.sol";
import "../types/PayoffData.sol";
import "../libraries/FullMath.sol";
import "../libraries/LogExpMath.sol";

/// @title PayoffFunctions
/// @notice Library for calculating Fee Compression Swap payoffs
library PayoffFunctions {
    using PayoffData for PayoffData.PayoffParams;
    
    /// @notice Calculate payoff for given parameters
    function calculatePayoff(
        PayoffData.PayoffParams memory params
    ) internal pure returns (uint256) {
        if (params.payoffType == PayoffData.PayoffType.LINEAR) {
            return _calculateLinearPayoff(params);
        } else if (params.payoffType == PayoffData.PayoffType.LOG) {
            return _calculateLogPayoff(params);
        } else if (params.payoffType == PayoffData.PayoffType.DIGITAL) {
            return _calculateDigitalPayoff(params);
        } else {
            revert("PayoffFunctions: unknown payoff type");
        }
    }
    
    /// @notice Linear variance swap payoff
    /// @dev Payoff = notional × (realizedVariance - strikeVariance)
    function _calculateLinearPayoff(
        PayoffData.PayoffParams memory params
    ) private pure returns (uint256) {
        int256 diff = int256(params.realizedVariance) - int256(params.strikeVariance);
        
        if (diff <= 0) {
            return 0;  // Floor at zero for long position
        }
        
        return FullMath.mulDiv(
            uint256(diff),
            params.notional,
            1e18  // Normalize from 18 decimals
        );
    }
    
    /// @notice Log payoff
    /// @dev Payoff = notional × (ln(realizedVariance) - ln(strikeVariance))
    function _calculateLogPayoff(
        PayoffData.PayoffParams memory params
    ) private pure returns (uint256) {
        require(params.realizedVariance > 0, "PayoffFunctions: realized must be > 0");
        require(params.strikeVariance > 0, "PayoffFunctions: strike must be > 0");
        
        int256 logRealized = LogExpMath.log(int256(params.realizedVariance));
        int256 logStrike = LogExpMath.log(int256(params.strikeVariance));
        
        int256 diff = logRealized - logStrike;
        
        if (diff <= 0) {
            return 0;  // Floor at zero for long position
        }
        
        return FullMath.mulDiv(
            uint256(diff),
            params.notional,
            1e18
        );
    }
    
    /// @notice Digital payoff
    /// @dev Payoff = notional if realizedVariance > strikeVariance, else 0
    function _calculateDigitalPayoff(
        PayoffData.PayoffParams memory params
    ) private pure returns (uint256) {
        if (params.realizedVariance > params.strikeVariance) {
            return params.notional;
        } else {
            return 0;
        }
    }
}
```

**Step 4: Run test to verify it passes**

```bash
forge test --match-test test_linearPayoff_calculatesCorrectly -vvv
# Expected: PASS
```

**Step 5: Commit**

```bash
git add src/interfaces/IPayoffFunction.sol src/types/PayoffData.sol src/payoff/PayoffFunctions.sol test/payoff/IPayoffFunction.t.sol
git commit -m "feat: implement extensible payoff function registry"
```

---

## Phase 3: Perpetual CFMM Core

### Task 4: Implement Fee Compression Swap Vault

**Files:**
- Create: `src/vault/FeeCompressionSwapVault.sol`
- Create: `src/interfaces/IFeeCompressionSwapVault.sol`
- Test: `test/vault/FeeCompressionSwapVault.t.sol`

**Step 1: Write the failing test**

```solidity
// test/vault/FeeCompressionSwapVault.t.sol

// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

import "forge-std/Test.sol";
import "../src/vault/FeeCompressionSwapVault.sol";
import "../src/oracle/UniswapV3FeeGrowthOracle.sol";

contract FeeCompressionSwapVaultTest is Test {
    FeeCompressionSwapVault public vault;
    UniswapV3FeeGrowthOracle public oracle;
    
    address public constant USER = address(0x1);
    address public constant POOL = 0x88e6A0c2dDD26FEEb64f039a2c41296FcB3f5640;
    
    function setUp() public {
        oracle = new UniswapV3FeeGrowthOracle();
        vault = new FeeCompressionSwapVault(
            address(oracle),
            address(0xUSDC)  // USDC address
        );
    }
    
    function test_deposit_collateral_mintsERC6909() public {
        uint256 depositAmount = 10_000e6;  // $10,000 USDC
        
        vm.startPrank(USER);
        // Mock USDC transfer
        vault.deposit(
            POOL,
            -2000,  // tickLower
            2000,   // tickUpper
            depositAmount,
            PayoffData.PayoffType.LINEAR,
            0.01e18  // strikeVariance
        );
        vm.stopPrank();
        
        // Should mint ERC6909 tokens representing the position
        uint256 balance = vault.balanceOf(USER, getPositionId(0));
        assertGt(balance, 0);
    }
    
    function test_calculateFundingRate_positive() public {
        // When realized variance > strike, longs receive funding
        uint256 fundingRate = vault.calculateFundingRate(
            getPositionId(0),
            0.015e18,  // realizedVariance
            0.01e18    // strikeVariance
        );
        
        assertGt(fundingRate, 0);
    }
    
    function test_settleFunding_transfersUSDC() public {
        // Setup position
        vm.startPrank(USER);
        vault.deposit(
            POOL,
            -2000,
            2000,
            10_000e6,
            PayoffData.PayoffType.LINEAR,
            0.01e18
        );
        vm.stopPrank();
        
        // Settle funding (mock oracle data)
        uint256 fundingPayment = vault.settleFunding(getPositionId(0));
        
        assertGt(fundingPayment, 0);
    }
    
    function test_withdraw_burnsERC6909() public {
        // Setup and deposit
        vm.startPrank(USER);
        vault.deposit(
            POOL,
            -2000,
            2000,
            10_000e6,
            PayoffData.PayoffType.LINEAR,
            0.01e18
        );
        
        // Withdraw
        uint256 withdrawn = vault.withdraw(getPositionId(0), 100%);
        
        assertGt(withdrawn, 0);
        vm.stopPrank();
    }
}
```

**Step 2: Run test to verify it fails**

```bash
forge test --match-test test_deposit_collateral_mintsERC6909 -vvv
# Expected: FAIL
```

**Step 3: Write minimal implementation**

```solidity
// src/vault/FeeCompressionSwapVault.sol

// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@ERC6909/ERC6909.sol";
import "../interfaces/IFeeGrowthOracle.sol";
import "../types/PayoffData.sol";
import "../payoff/PayoffFunctions.sol";

/// @title FeeCompressionSwapVault
/// @notice Perpetual Fee Compression Swap vault with ERC6909 tokenization
contract FeeCompressionSwapVault is ERC6909 {
    using SafeERC20 for IERC20;
    using PayoffData for PayoffData.PayoffParams;
    
    /// @notice Oracle for fee growth data
    IFeeGrowthOracle public immutable oracle;
    
    /// @notice Collateral token (USDC)
    IERC20 public immutable collateralToken;
    
    /// @notice Position data
    struct Position {
        address pool;
        int24 tickLower;
        int24 tickUpper;
        PayoffData.PayoffType payoffType;
        uint256 strikeVariance;
        uint256 notional;
        uint256 lastFundingTime;
        int256 accumulatedFunding;
    }
    
    /// @notice Position ID => Position data
    mapping(bytes32 => Position) public positions;
    
    /// @notice Owner => Position ID => Balance
    mapping(address => mapping(bytes32 => uint256)) public positionBalances;
    
    /// @notice Total collateral in vault
    uint256 public totalCollateral;
    
    /// @notice Funding settlement interval (e.g., 8 hours)
    uint256 public constant FUNDING_INTERVAL = 8 hours;
    
    /// @notice Events
    event PositionOpened(
        address indexed owner,
        bytes32 indexed positionId,
        address pool,
        uint256 notional
    );
    
    event FundingSettled(
        bytes32 indexed positionId,
        int256 fundingAmount,
        uint256 timestamp
    );
    
    event PositionClosed(
        address indexed owner,
        bytes32 indexed positionId,
        uint256 collateralReturned
    );
    
    constructor(
        address _oracle,
        address _collateralToken
    ) ERC6909("Fee Compression Swap Position", "FCSP") {
        oracle = IFeeGrowthOracle(_oracle);
        collateralToken = IERC20(_collateralToken);
    }
    
    /// @notice Deposit collateral and open position
    function deposit(
        address pool,
        int24 tickLower,
        int24 tickUpper,
        uint256 notional,
        PayoffData.PayoffType payoffType,
        uint256 strikeVariance
    ) external returns (bytes32 positionId) {
        // Transfer collateral from user
        collateralToken.safeTransferFrom(msg.sender, address(this), notional);
        
        // Generate position ID
        positionId = _generatePositionId(
            msg.sender,
            pool,
            tickLower,
            tickUpper,
            payoffType,
            strikeVariance
        );
        
        // Store position data
        positions[positionId] = Position({
            pool: pool,
            tickLower: tickLower,
            tickUpper: tickUpper,
            payoffType: payoffType,
            strikeVariance: strikeVariance,
            notional: notional,
            lastFundingTime: block.timestamp,
            accumulatedFunding: 0
        });
        
        // Mint ERC6909 tokens
        _mint(msg.sender, positionId, notional);
        
        // Update total collateral
        totalCollateral += notional;
        
        emit PositionOpened(msg.sender, positionId, pool, notional);
    }
    
    /// @notice Calculate funding rate for position
    function calculateFundingRate(
        bytes32 positionId,
        uint256 realizedVariance,
        uint256 strikeVariance
    ) public pure returns (uint256) {
        // Funding rate = (realized - strike) / funding interval
        int256 diff = int256(realizedVariance) - int256(strikeVariance);
        
        if (diff <= 0) {
            return 0;
        }
        
        // Annualized funding rate
        return uint256(diff) * (365 days / FUNDING_INTERVAL);
    }
    
    /// @notice Settle funding for a position
    function settleFunding(
        bytes32 positionId
    ) external returns (uint256 fundingPayment) {
        Position storage position = positions[positionId];
        require(position.notional > 0, "FeeCompressionSwapVault: position not found");
        
        // Check if funding interval has passed
        require(
            block.timestamp >= position.lastFundingTime + FUNDING_INTERVAL,
            "FeeCompressionSwapVault: funding not due"
        );
        
        // Get realized variance from oracle
        bytes32[] memory positionIds = new bytes32[](1);
        positionIds[0] = positionId;
        
        FeeGrowthData.VarianceResult memory varianceResult = oracle.calculateVariance(
            position.pool,
            position.tickLower,
            position.tickUpper,
            positionIds
        );
        
        // Calculate funding payment
        PayoffData.PayoffParams memory params = PayoffData.PayoffParams({
            notional: position.notional,
            strikeVariance: position.strikeVariance,
            realizedVariance: varianceResult.variance,
            payoffType: position.payoffType
        });
        
        int256 fundingAmount = int256(PayoffFunctions.calculatePayoff(params));
        
        // Update accumulated funding
        position.accumulatedFunding += fundingAmount;
        position.lastFundingTime = block.timestamp;
        
        // Transfer funding payment
        if (fundingAmount > 0) {
            fundingPayment = uint256(fundingAmount);
            require(
                fundingPayment <= totalCollateral,
                "FeeCompressionSwapVault: insufficient collateral"
            );
            collateralToken.safeTransfer(msg.sender, fundingPayment);
            totalCollateral -= fundingPayment;
        }
        
        emit FundingSettled(positionId, fundingAmount, block.timestamp);
    }
    
    /// @notice Withdraw collateral and close position
    function withdraw(
        bytes32 positionId,
        uint256 percentage
    ) external returns (uint256 collateralReturned) {
        Position storage position = positions[positionId];
        require(position.notional > 0, "FeeCompressionSwapVault: position not found");
        require(msg.sender == ownerOf(positionId), "FeeCompressionSwapVault: not owner");
        
        // Settle outstanding funding
        if (block.timestamp >= position.lastFundingTime + FUNDING_INTERVAL) {
            settleFunding(positionId);
        }
        
        // Calculate collateral to return
        uint256 positionCollateral = (position.notional * percentage) / 100;
        
        // Burn ERC6909 tokens
        _burn(msg.sender, positionId, positionCollateral);
        
        // Transfer collateral
        collateralToken.safeTransfer(msg.sender, positionCollateral);
        totalCollateral -= positionCollateral;
        
        // Update position
        if (percentage == 100%) {
            delete positions[positionId];
        } else {
            position.notional -= positionCollateral;
        }
        
        emit PositionClosed(msg.sender, positionId, positionCollateral);
        collateralReturned = positionCollateral;
    }
    
    /// @notice Generate unique position ID
    function _generatePositionId(
        address owner,
        address pool,
        int24 tickLower,
        int24 tickUpper,
        PayoffData.PayoffType payoffType,
        uint256 strikeVariance
    ) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(
            owner,
            pool,
            tickLower,
            tickUpper,
            payoffType,
            strikeVariance,
            block.timestamp,
            block.number
        ));
    }
    
    /// @notice Get position balance for owner
    function balanceOf(
        address owner,
        bytes32 positionId
    ) public view override returns (uint256) {
        return positionBalances[owner][positionId];
    }
    
    /// @notice Get position owner (simplified for MVP)
    function ownerOf(
        bytes32 positionId
    ) public view returns (address) {
        // In production, maintain owner mapping
        // For MVP, this is a placeholder
        return address(0);
    }
}
```

**Step 4: Run test to verify it passes**

```bash
forge test --match-test test_deposit_collateral_mintsERC6909 -vvv
# Expected: PASS (may need ERC6909 base contract)
```

**Step 5: Commit**

```bash
git add src/vault/FeeCompressionSwapVault.sol src/interfaces/IFeeCompressionSwapVault.sol test/vault/FeeCompressionSwapVault.t.sol
git commit -m "feat: implement perpetual FCS vault with ERC6909 tokenization"
```

---

## Phase 4: Integration & Testing

### Task 5: Create End-to-End Integration Test

**Files:**
- Create: `test/integration/FeeCompressionSwap.t.sol`
- Modify: `foundry.toml` (add mainnet fork config)

**Step 1: Write integration test**

```solidity
// test/integration/FeeCompressionSwap.t.sol

// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

import "forge-std/Test.sol";
import "../../src/vault/FeeCompressionSwapVault.sol";
import "../../src/oracle/UniswapV3FeeGrowthOracle.sol";

contract FeeCompressionSwapIntegrationTest is Test {
    FeeCompressionSwapVault public vault;
    UniswapV3FeeGrowthOracle public oracle;
    
    address public USER1 = address(0x1);
    address public USER2 = address(0x2);
    
    // Mainnet addresses
    address constant USDC = 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
    address constant ETH_USDC_POOL = 0x88e6A0c2dDD26FEEb64f039a2c41296FcB3f5640;
    
    function setUp() public {
        // Fork mainnet
        vm.createSelectFork(vm.envString("MAINNET_RPC_URL"));
        
        // Deploy contracts
        oracle = new UniswapV3FeeGrowthOracle();
        vault = new FeeCompressionSwapVault(address(oracle), USDC);
        
        // Fund users with USDC
        deal(USDC, USER1, 100_000e6);
        deal(USDC, USER2, 100_000e6);
    }
    
    function test_fullLifecycle_depositHoldWithdraw() public {
        // User 1 opens long position
        vm.startPrank(USER1);
        IERC20(USDC).approve(address(vault), 10_000e6);
        
        bytes32 positionId = vault.deposit(
            ETH_USDC_POOL,
            -2000,
            2000,
            10_000e6,
            PayoffData.PayoffType.LINEAR,
            0.01e18
        );
        vm.stopPrank();
        
        // Verify position created
        assertEq(vault.totalCollateral(), 10_000e6);
        
        // Fast forward time (simulate funding period)
        vm.warp(block.timestamp + 8 hours + 1);
        
        // Settle funding
        vm.prank(USER1);
        uint256 fundingPayment = vault.settleFunding(positionId);
        
        // User 1 withdraws
        vm.prank(USER1);
        uint256 withdrawn = vault.withdraw(positionId, 100%);
        
        // Should get back collateral + funding
        assertGt(withdrawn, 10_000e6 - 1e6);  // Within 1% tolerance
    }
    
    function test_multiplePositions_differentPayoffTypes() public {
        // User 1: Linear payoff
        vm.startPrank(USER1);
        IERC20(USDC).approve(address(vault), 10_000e6);
        bytes32 position1 = vault.deposit(
            ETH_USDC_POOL,
            -2000,
            2000,
            10_000e6,
            PayoffData.PayoffType.LINEAR,
            0.01e18
        );
        vm.stopPrank();
        
        // User 2: Digital payoff
        vm.startPrank(USER2);
        IERC20(USDC).approve(address(vault), 10_000e6);
        bytes32 position2 = vault.deposit(
            ETH_USDC_POOL,
            -2000,
            2000,
            10_000e6,
            PayoffData.PayoffType.DIGITAL,
            0.01e18
        );
        vm.stopPrank();
        
        // Both positions should exist
        assertEq(vault.totalCollateral(), 20_000e6);
    }
}
```

**Step 2: Update foundry.toml**

```toml
# Add to foundry.toml

[rpc_endpoints]
mainnet = "${MAINNET_RPC_URL}"

[fuzz]
runs = 256
max_test_rejects = 65536

[invariant]
runs = 100
depth = 50
```

**Step 3: Run integration test**

```bash
forge test --match-test test_fullLifecycle_depositHoldWithdraw -vvv --fork-url $MAINNET_RPC_URL
# Expected: PASS (requires mainnet fork)
```

**Step 4: Commit**

```bash
git add test/integration/FeeCompressionSwap.t.sol foundry.toml
git commit -m "test: add end-to-end integration tests for FCS vault"
```

---

## Deliverables Checklist

- [ ] **Phase 1: Oracle & Data Infrastructure**
  - [ ] FeeGrowth oracle interface and types
  - [ ] Uniswap V3 oracle implementation
  - [ ] Oracle unit tests

- [ ] **Phase 2: Payoff Function Registry**
  - [ ] Payoff function interface
  - [ ] Linear, Log, Digital implementations
  - [ ] Payoff function tests

- [ ] **Phase 3: Perpetual CFMM Core**
  - [ ] FCS vault with ERC6909
  - [ ] Funding settlement logic
  - [ ] Vault unit tests

- [ ] **Phase 4: Integration & Testing**
  - [ ] End-to-end integration tests
  - [ ] Mainnet fork tests
  - [ ] Gas optimization audit

---

## Validation: Derivative Viability

**If the hypothesis is proved (variance ≈ ln(P_{#LP})), the derivative is viable because:**

1. **Observable Underlying:** Fee growth data is on-chain and verifiable via oracle
2. **Settlement Mechanism:** Oracle-reported variance enables cash settlement
3. **Replication:** Static portfolio of range accrual notes can back the vault
4. **Tokenization:** ERC6909 enables efficient multi-position management
5. **Perpetual Structure:** Funding model matches LP hedging needs
6. **Extensibility:** Payoff registry supports multiple contract types

**Key Assumptions:**
- Oracle can reliably report feeGrowth data
- Variance calculation is manipulation-resistant
- Sufficient collateral backs positions
- Funding settlement is solvent

---

**Plan complete and saved to `docs/plans/2026-02-24-fee-compression-swap-implementation.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**

**If Subagent-Driven chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:subagent-driven-development
- Stay in this session
- Fresh subagent per task + code review

**If Parallel Session chosen:**
- Guide to open new session in worktree
- **REQUIRED SUB-SKILL:** New session uses superpowers:executing-plans