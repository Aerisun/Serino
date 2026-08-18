export type ImageLoadPriority = "foreground" | "background";

type ImageLoadTask = {
  priority: ImageLoadPriority;
  start: () => void;
  started: boolean;
  finished: boolean;
};

export interface ImageLoadQueueHandle {
  finish: () => void;
  promote: () => ImageLoadQueueHandle;
  cancel: () => void;
}

export interface ImageLoadQueue {
  enqueue: (priority: ImageLoadPriority, start: () => void) => ImageLoadQueueHandle;
  resumeBackground: () => void;
}

export function createImageLoadQueue(): ImageLoadQueue {
  const backgroundTasks: ImageLoadTask[] = [];
  let backgroundEnabled = false;
  let activeForegroundCount = 0;
  let activeBackgroundTask: ImageLoadTask | null = null;

  const removeBackgroundTask = (task: ImageLoadTask) => {
    const index = backgroundTasks.indexOf(task);
    if (index >= 0) {
      backgroundTasks.splice(index, 1);
    }
  };

  const startTask = (task: ImageLoadTask) => {
    if (task.started || task.finished) {
      return;
    }

    task.started = true;
    if (task.priority === "foreground") {
      activeForegroundCount += 1;
    } else {
      activeBackgroundTask = task;
    }

    try {
      task.start();
    } catch {
      finishTask(task);
    }
  };

  const drainBackground = () => {
    if (!backgroundEnabled || activeForegroundCount > 0 || activeBackgroundTask) {
      return;
    }

    const nextTask = backgroundTasks.shift();
    if (nextTask) {
      startTask(nextTask);
    }
  };

  const finishTask = (task: ImageLoadTask) => {
    if (task.finished) {
      return;
    }

    task.finished = true;
    if (task.priority === "foreground") {
      activeForegroundCount = Math.max(0, activeForegroundCount - 1);
    } else if (activeBackgroundTask === task) {
      activeBackgroundTask = null;
    } else {
      removeBackgroundTask(task);
    }

    drainBackground();
  };

  const createHandle = (task: ImageLoadTask): ImageLoadQueueHandle => ({
    finish: () => finishTask(task),
    promote: () => {
      if (task.finished || task.priority === "foreground") {
        return createHandle(task);
      }

      if (activeBackgroundTask === task) {
        activeBackgroundTask = null;
        task.priority = "foreground";
        activeForegroundCount += 1;
        return createHandle(task);
      } else {
        removeBackgroundTask(task);
      }

      task.priority = "foreground";
      startTask(task);
      return createHandle(task);
    },
    cancel: () => finishTask(task),
  });

  return {
    enqueue: (priority, start) => {
      const task: ImageLoadTask = {
        priority,
        start,
        started: false,
        finished: false,
      };

      if (priority === "foreground") {
        startTask(task);
      } else {
        backgroundTasks.push(task);
        drainBackground();
      }

      return createHandle(task);
    },
    resumeBackground: () => {
      backgroundEnabled = true;
      drainBackground();
    },
  };
}
