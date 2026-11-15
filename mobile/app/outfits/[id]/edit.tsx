// /outfits/{id}/edit — edit a saved set: the same builder, pre-filled with
// the set's name and items. The [id] folder makes {id} part of the address.
import { useLocalSearchParams } from "expo-router";

import { BuilderScreen } from "../../../src/outfits/BuilderScreen";

export default function EditSet() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <BuilderScreen outfitId={id} />;
}
