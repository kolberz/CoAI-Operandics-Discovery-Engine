import Lake
open Lake DSL

package coai where
  -- no-sorries removed because the compiler doesn't support it natively yet

require mathlib from git
  "https://github.com/leanprover-community/mathlib4.git"

lean_lib CoAI where
  -- add library configuration options here

@[default_target]
lean_exe coai where
  root := `Main
