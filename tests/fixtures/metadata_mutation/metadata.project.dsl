dsl v1.0

// Real FreeCAD metadata mutation and observation coexistence proof.
// Semantic target names intentionally differ from native object names for the
// metadata owner and the deletion target.

profile MetadataMutationCoexistence {
  output_dir = "metadata"
  metadata_enabled = true
}

use profile MetadataMutationCoexistence

product MetadataCoexistence {
  adapter      = "freecad"
  source_model = "metadata_coexistence_model"
  outputs      = ["none"]

  // Native VarSet pilotValue parameter assignment; coexists with metadata writes.
  param pilotValue: number = 12.5

  // Semantic target Enclosure is native MetadataBody. Hide is a real native
  // visibility mutation and does not affect the Body shape.
  target Enclosure:
    action = hide
    metadata material = "S235JR" { }
    metadata tagged = true
    metadata mass = 12.5
    metadata revision = 7
    metadata tolerance = 0.75
    metadata sequence = 20

  // Native Pad suppression coexists with metadata and parameter assignment.
  target Pad: action = suppress

  // Semantic target SacrificialMarker is native DeletionMarker. The standalone
  // Part::Feature has no native dependents and does not affect Body validity.
  target SacrificialMarker: action = delete
}
