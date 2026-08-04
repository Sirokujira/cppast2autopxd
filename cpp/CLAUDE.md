# Claude Code Operating Rules

## Default workflow

- Do not start implementation immediately.
- First, inspect the repository structure, relevant files, tests, and existing conventions.
- Produce a short implementation plan before editing files.
- Split work into investigation, design, implementation, testing, and review phases.
- Use subagents for isolated heavy tasks when they add value, especially:
  - broad codebase investigation
  - design review
  - test planning
  - security or regression review
- Do not use subagents as a generic search engine.
- Subagents must return concrete findings tied to files, symbols, tests, or implementation decisions.
- Keep all work tied to the current user goal. Do not invent unrelated tasks just to stay busy.

## Understanding gate

Before implementation, confirm that the user understands the planned change.

Implementation is forbidden until all of the following are satisfied:

1. The target behavior is stated clearly.
2. The affected files or modules are identified.
3. The test or verification method is identified.
4. The user has answered at least one comprehension-check question.

Ask the user a short question such as:

> My understanding is that we will change X by editing Y and verify it with Z. Is that correct? Also, what should happen in edge case A?

Only after the user answers, proceed to implementation.

## Autonomous development loop

When implementation is allowed:

1. Pick the next highest-value task from the plan.
2. Implement the smallest coherent change.
3. Run the relevant test, lint, typecheck, build, or reproduction command.
4. Fix failures.
5. Ask a reviewer subagent to inspect the diff against the plan.
6. Apply necessary fixes.
7. Report:
   - changed files
   - verification commands
   - remaining risks
   - next recommended task

Do not continue into unrelated work without a clear goal.