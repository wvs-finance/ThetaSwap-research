

1. Build model
### Model Assumptions


### Model Construction

1 . Two pools with the same underlying:
1.2. One of the tokens is a unit of account token (numeraire)
1.3  token Approval of routers, etc

1.4  The traders do not have identity, they are address(this) on tests, thisb is beacuase we = do not care on their dynacmis since we are assuming they are all the same (uninformed) we care about the inducesd flow following a mean-reversion




- fixed external price ==> CFMM is primary market

struct FixedMarketPrice{
       uint160 lastPrice
       PoolId referenceMarket
}

function poolId(FixedMarketPrice) returns(PoolId) 
function lastPrice(FixedMarketPrice) returns(uint160)

function fixedMarketPrice(PoolId){
	 require(StateLibrary.slot0(poolId()) == lastPrice())
}


===> All trading volume is mean reverting (rule)

This needs formal verification

type MeanRevertingVolume(vm.snapshot(state)):
     require(isInvese(swapDeltaPrevious, swapDeltaNow);



===> IL = 0 (invariant)
// Adapt the v3-peripohery/PositionValue to 
here

// This needs formal verification.

This is rule is for every subsequent trades the implermanent loss markout
of all liqudity providers is zero ///

type PositionValueMarkout(positionKey,afterSwapDelta) --> BalanceDelta:

type impermanentLossMarkout(positionKey,afterSwapDelta) --> BalanceDelta:
     require(impermanentLossBefore == impermentLossAfter  ==0)




===> JIT probability of arriaval is always 1

// This needs formal verification too 
     ==> This is embedded on the JITHook where the JIT always provides liquidity
     sufficient to fulfill the swap
     		==> No swap can exceed JITLiquidityOnSwap


(rule)


===> All swaps do not exhaust JIT liquidity


value(\sum (swaps)) <= value(representativeLPPosition) -> (invariant)

To show pro-rata price competition:

   ==> JIT does not know he can theoretically fulfill all trades
        ==> For all trades he provides excess liquidity ==> It exhausts it faster than PLP
	===> 

	==> At time zero there are two LP's on each pool:
	    ==> pool 1: one jit ^ one plp
	    ==> pool 2: one plp ^ one plp
        ==> All liquidity providers have same initial capital

==> Since price do not affect volume
    ==> demand is uncertain to LP's.
    ==> demand is perfectly elastic to liquidity depth (from capponi)

    	==> passive LP's provide liquidity that maxmizes the demand subject to the
         perfect elasticity only available information they know

       ==> JIT excess liquidity is a function of passive liquidity this is an optimization
       problem of they provindg the liquidity such that they do not disscourage passive LP's
       Thus they let passive LP's only earn the same as interest rate


       ==> Note that in this model since there is no market risk, the JIT only allows PLP
       to finance the gas costs + surplues

       ==> For every swap enters a LP with same capital as the others and solves the alsticity opti-
       mization problem and provides passive liquidity

       ==> Optimal tick range is alwys the same snce there is no volatility

       ==> Each swap crosses the tickRange ==> triggers fee revenue collection

       ==> The same behavor happens for both pools

==> The only thing that changes is that in one pool on passive LP has access to an instrument that pays
one unit of account per liquidity provider that enters the pool.


==> Result: The PLP that uses the surplus share he has to buy the instrument while the others LP's on both pools re-invest the surplus as liquidity


- Show that the PLP  hedges the competition risk
- Show that the competition risk is the only risk associated with passive liquidity provision in this model



