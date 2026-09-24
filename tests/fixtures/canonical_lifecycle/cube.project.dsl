dsl v1.0

// Canonical FreeCAD lifecycle fixture:
// table-driven parameter assignments plus native target mutations.

profile CubeCanonicalLifecycle {
  output_dir = "cube"
  metadata_enabled = true
}

use profile CubeCanonicalLifecycle

product CubeBox {
  adapter      = "freecad"
  source_model = "cube_canonical_lifecycle_model"
  outputs      = ["none"]

  /*
   * The committed FreeCAD fixture matches the "small" row.
   * Default to "large" so normal execution performs real native
   * parameter changes rather than rewriting the existing values.
   */
  param variant: string = "large"

  param boxLength:  number = table_cell("cube_variants", variant, "boxLength")
  param boxWidth:   number = table_cell("cube_variants", variant, "boxWidth")
  param boxHeight:  number = table_cell("cube_variants", variant, "boxHeight")
  param holeDia:    number = table_cell("cube_variants", variant, "holeDia")
  param boxChamfer: number = table_cell("cube_variants", variant, "boxChamfer")

  // Headless FreeCAD visibility recovery.
  target Body:    action = unhide
  target Body001: action = unhide
  target Chamfer: action = unhide
  target Pad002:  action = unhide

  // Canonical target-mutation families.
  target Fillet:    action = suppress
  target Pocket001: action = unsuppress
  target Body003:   action = hide
  target Body002:   action = delete
}
