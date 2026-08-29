export const isAbsolutePath = (value: string): boolean => value.startsWith("/") || /^[A-Za-z]:[\\/]/.test(value);

export const isAbsoluteExecutablePath = (value: string): boolean =>
  isAbsolutePath(value) && value.toLocaleLowerCase().endsWith(".exe");
