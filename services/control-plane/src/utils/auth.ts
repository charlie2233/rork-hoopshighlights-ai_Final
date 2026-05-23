export function isSharedSecretAuthorized(actual: string | null, expected: string | undefined): boolean {
  if (!expected) {
    return true;
  }
  if (!actual) {
    return false;
  }
  const left = new TextEncoder().encode(actual);
  const right = new TextEncoder().encode(expected);
  if (left.length !== right.length) {
    return false;
  }
  let result = 0;
  for (let index = 0; index < left.length; index += 1) {
    const leftByte = left[index]!;
    const rightByte = right[index]!;
    result |= leftByte ^ rightByte;
  }
  return result === 0;
}
