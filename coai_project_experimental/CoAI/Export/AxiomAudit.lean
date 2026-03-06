import CoAI.CertifiedStack
import CoAI.NormalizedAttention

#eval IO.println "=== certified_attention_contract ==="
#print axioms StochasticAttention.certified_attention_contract

#eval IO.println "=== certified_normalized_attention_contract_strict ==="
#print axioms StochasticAttention.certified_normalized_attention_contract_strict
