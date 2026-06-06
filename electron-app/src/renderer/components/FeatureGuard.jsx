import { FEATURES } from '../config';

export default function FeatureGuard({ flag, children }) {
  return FEATURES[flag] ? children : null;
}
