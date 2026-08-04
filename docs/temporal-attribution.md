# Excursion attribution in shared coordinator workstreams

Status: design note and review companion for issue #954.

This note uses the vocabulary already established by `PRIMER.md` and
`HYPOTHESIS.md`. It deliberately avoids “priority”: Turnstone already uses
priority for message scheduling, while the property here is identity and
causality.

## The claim

*Informal.* A workstream has a durable **owner**, but each trigger-to-ready
**excursion** has a **trusted principal**. Per-user credentials must follow the
excursion's causal lineage, not the workstream owner, the most recent sender,
or the most recently completed child.

*In plain terms.* Jared can own a coordinator forever without every future
action being Jared's. A human message starts an excursion as that human. A
spawn edge carries that trusted principal into the child while preserving
Jared as the child's tenant owner. The child's terminal ledger returns as the
parent's effect record; when that record is the cause of continued work, its
trusted principal returns with it.

*Operationally.* The shell owns a durable tuple

```text
(excursion_id, principal_id, cause_action_id, cause_workstream_id)
```

and permits one of two states at an action boundary:

1. attribution is **resolved** to exactly one trusted principal; or
2. attribution is **ambiguous**, in which case per-user delegated auth fails
   closed until a new human trigger begins an excursion or an authorized action
   names a trusted causal workstream.

The model may propose `cause_workstream_id`. It may never propose
`principal_id`. The authorization gate verifies that the cause is in the
coordinator's own subtree and reads its shell-persisted attribution.

## Why owner and last sender are both falsified

### Scenario A: a shared interactive workstream

1. Jared creates workstream `W`, sends a message, and completes an excursion.
2. John enters the shared project and sends: “I have the Certbot permission;
   try again with mine.”
3. The next model and tool calls must use John's delegated credentials.
4. The harness reaches its stop token and returns to ready.
5. Jared sends the next message.
6. The next excursion must use Jared's delegated credentials.

The durable owner rule fails at step 3. A mutable global “last sender” happens
to work here only because the stop token serializes the two excursions.

### Scenario B: independent coordinator fan-out

1. Jared's message starts excursion `EJ` and spawns children A, B, and C.
2. Each spawn is an authorized action. A, B, and C keep owner Jared for tenancy
   and inherit trusted principal Jared through their spawn edges.
3. After the coordinator returns to ready, John's message starts excursion
   `EN` and spawns D and E.
4. D and E keep owner Jared but inherit trusted principal John.

Changing child ownership to John is not the repair: it breaks subtree tenancy
and confuses “whose durable object is this?” with “whose authority caused this
run?”

### Scenario C: B returns after John spoke

1. The coordinator's last human sender is John.
2. Child B, descended from `EJ`, reaches its halt and persists its terminal
   ledger.
3. If the coordinator waits on B, B's result enters the parent as an effect
   record at the tool-result boundary.
4. Before the next model run, the shell restores Jared as the trusted principal
   from B's persisted attribution.
5. Work causally continued from B therefore spawns as Jared, not John.

This is the minimal counterexample to last-sender attribution. Wall-clock
recency and causal ancestry disagree, and only the latter is an authorization
fact.

### Scenario D: B returns while another tool call is in flight

A child completion does not splice itself into a running model generation or
an unrelated tool call. The child state and transcript are persisted, an SSE
event is emitted, and the child event bus wakes an active
`wait_for_workstream` waiter if one exists. With no waiter, the notification is
observational; the idle-coordinator liveness nudge can prompt a later wait.

The return becomes model input only when a wait/inspect effect is folded back
by the parent shell. Attribution changes at that deterministic fold boundary,
not at arbitrary completion time. This preserves the stopped-process shape:
asynchronous environment timing is a coin in `Q_E`; `rho` still owns when the
observed receipt becomes controller state.

### Scenario E: Jared's B and John's D return together

If one wait result lowers both terminal effect records into the next context,
neither arrival order nor list order can choose a trusted principal. The join
is explicitly ambiguous. The same rule applies when separate wait tool calls
run in one parallel batch: the shell folds all sibling receipts together only
after the batch settles, so executor completion order cannot pick an identity.

An `entra_obo` coordinator model must fail closed at that point: the model
inference is itself a delegated action, so asking the model which user it meant
to run as would already require choosing a user's token. A deployment that
intentionally synthesizes mixed-principal results must configure the
coordinator lane with `entra_app` (or another explicit deployment identity).
From that neutral lane, a subsequent child action may cite one causal
workstream; the shell resolves its trusted principal and the normal approval
gate authorizes the spawn/send. There is no silent runtime fallback from OBO to
app identity.

An OBO-only coordinator can avoid the join by collecting and processing one
causal lane at a time. Waiting on B alone restores Jared before the next model
run; waiting on D alone restores John.

## Derived rules

1. **Owner is tenancy, not execution identity.** JWT `sub`, workstream rows,
   project membership, and subtree ownership remain bound to the durable owner.
2. **Trusted principal is excursion control state.** Model backend OBO, MCP
   user pools, delegated-action audit attribution, and child propagation read
   the excursion principal.
3. **Attribution is signed and durable.** Coordinator JWT custom claims carry
   it through console-to-node routing; `workstream_config` restores it before a
   rehydrated session can perform autonomous work.
4. **Spawn attenuates authority.** A child inherits the parent's resolved
   principal along a spawn edge. The body cannot name a user, and ownership
   does not change.
5. **Child completion is an effect record.** A terminal child's attribution is
   returned alongside its wait result and folded before the next model run.
6. **A causal join is not a race.** Multiple distinct principals produce an
   ambiguous state; no ordering heuristic chooses a credential.
7. **Auxiliary lanes do not invent identities.** Judge, output guard,
   perception, MCP, and the primary model all resolve through the same
   excursion state. A lane that needs neutral multi-principal synthesis must be
   configured with app identity explicitly.
8. **Shared transcript visibility is a separate policy.** This design accepts
   the current project/workstream co-working domain: members may see content
   other members caused the system to retrieve. It prevents credential
   misattribution; it does not create per-message transcript tenancy.

## Implementation shape in this branch

- `ExcursionAttribution` defines one versioned config/claim representation.
- A fresh authenticated human send creates a new excursion, including when the
  same user sent the previous completed turn.
- Coordinator tokens keep the owner in `sub` and add signed excursion claims.
- The console routing proxy preserves those claims when it re-mints for a node.
- Child create/send handlers accept attribution only from a validated
  coordinator token; request JSON cannot supply it.
- Session rehydration restores resolved or ambiguous attribution before model
  and MCP use.
- `wait_for_workstream` returns terminal-child attribution. The coordinator
  adopts one principal, joins same-principal branches under a fresh excursion,
  or records a mixed-principal ambiguity.
- `spawn_workstream`, `spawn_batch`, and `send_to_workstream` accept an optional
  `cause_workstream_id`. In an ambiguous state it is required; the shell
  resolves it through the owned-subtree gate and stamps the outgoing action.

This is control-plane attribution, not yet the full per-action-capability ideal
from `HYPOTHESIS.md`: the signed JWT binds the routed request and its causal
action id, while downstream OAuth providers may still mint audience-scoped
tokens rather than credentials cryptographically restricted to one
`action_id`. The branch closes principal selection and propagation; provider
token attenuation remains a separate layer.

## Falsifiers

The implementation is wrong if any of these observations is possible:

- John's human-triggered excursion mints or dispatches with Jared's OBO token
  because Jared owns the coordinator.
- B's returned ledger continues under John merely because John was the last
  human sender.
- a request body can set `principal_id` or forge excursion lineage;
- child ownership changes to the acting principal and escapes the owner's
  subtree;
- a mixed Jared/John result selects either token by completion, list, or message
  order;
- rehydration performs a model/tool action before restoring the persisted
  attribution state;
- an auxiliary lane resolves a different user from the primary lane for the
  same excursion; or
- an OBO failure silently changes grant type to app identity.

## Relation to issue #954's permission question

This ruling answers what a model-auth configuration gate is protecting: OBO is
allowed in shared sessions only while the current excursion has one resolved
trusted principal. Shared transcript visibility remains the accepted project
co-working property. Mixed-principal synthesis uses an explicitly configured
app lane or fails closed.

It does not decide whether the configuration capability should be
`admin.model_auth` or a host allow-list. That is an orthogonal gate-placement
decision: attribution determines *whose credential may be minted*; destination
confinement determines *where that credential may be sent*. Neither substitutes
for the other.
