import { initActionStates } from "./core/action-state.js";
import { initActivityIndicator } from "./core/activity.js";
import { initToasts } from "./core/toast.js";
import { initProductCustomizer } from "./modules/product.js";
import { initPwa } from "./core/pwa.js";

initActivityIndicator();
initActionStates();
initToasts();
initProductCustomizer();
initPwa();
