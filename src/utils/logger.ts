type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR";

const log = (level: LogLevel, background: string, ...args: unknown[]) => {
  const prefix = `%c Trainer Relay ${level} `;
  const style = `background: ${background}; color: black;`;
  switch (level) {
    case "DEBUG":
      console.debug(prefix, style, ...args);
      return;
    case "INFO":
      console.info(prefix, style, ...args);
      return;
    case "WARNING":
      console.warn(prefix, style, ...args);
      return;
    case "ERROR":
      console.error(prefix, style, ...args);
      return;
  }
};

export const logger = {
  debug: (...args: unknown[]) => {
    log("DEBUG", "#1a96bc", ...args);
  },

  info: (...args: unknown[]) => {
    log("INFO", "#1abc9c", ...args);
  },

  warning: (...args: unknown[]) => {
    log("WARNING", "#ffbb00", ...args);
  },

  error: (...args: unknown[]) => {
    log("ERROR", "#bb0000", ...args);
  },
};
