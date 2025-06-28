console.log("functions.js loaded!");

function handleMeasurementButton(n_clicks) {
    console.log("Clientside callback triggered with n_clicks:", n_clicks);
    console.log("window.dashExtensions:", window.dashExtensions);
    
    if (n_clicks) {
        // Try multiple ways to access the function
        if (window.dashExtensions && window.dashExtensions.default && window.dashExtensions.default.startMeasurement) {
            console.log("Calling startMeasurement via dashExtensions.default");
            window.dashExtensions.default.startMeasurement();
            return n_clicks;
        } else if (window.startMeasurement) {
            console.log("Calling startMeasurement directly from window");
            window.startMeasurement();
            return n_clicks;
        } else {
            console.log("startMeasurement function not found, trying direct approach");
            // Direct approach as fallback
            const measureInteraction = document.querySelector('.leaflet-control-measure-interaction.js-interaction');
            if (measureInteraction) {
                measureInteraction.style.display = 'block';
                const startPrompt = measureInteraction.querySelector('.js-startprompt.startprompt');
                if (startPrompt) {
                    startPrompt.style.display = 'block';
                    setTimeout(() => {
                        const startButton = startPrompt.querySelector('.js-start.start');
                        if (startButton) {
                            console.log("Direct clicking start button");
                            startButton.click();
                        }
                    }, 100);
                }
            }
            return n_clicks;
        }
    }
    
    console.log("Conditions not met for startMeasurement");
    return window.dash_clientside.no_update;
}

function getAreaCoords(e) {
    if (e && Array.isArray(e.points)) {
        // Map each point to [lat, lng]
        const coords = e.points.map(pt => [pt.lng, pt.lat]);
        console.log("coords", coords);
        return {coordinates: coords};
    }

    return {coordinates: []};
}

function startMeasurement() {
    console.log("Toggle measurement tool programmatically");
    
    try {
        // Check if measurement is currently active
        const measuringPrompt = document.querySelector('.js-measuringprompt');
        const startPrompt = document.querySelector('.js-startprompt.startprompt');
        
        // If measurement is active (measuringprompt is visible), finish it
        if (measuringPrompt && measuringPrompt.style.display !== 'none') {
            console.log("Measurement is active, finishing it");
            const finishButton = document.querySelector('.js-finish.finish');
            if (finishButton) {
                console.log("Found finish button, clicking it");
                const finishEvent = new MouseEvent('click', {
                    view: window,
                    bubbles: true,
                    cancelable: true
                });
                finishButton.dispatchEvent(finishEvent);
                setDrawingButtonState(false); // Set button to inactive state
                return;
            }
        }
        
        // Otherwise, start measurement
        console.log("Starting new measurement");
        const measureToggle = document.querySelector('.leaflet-control-measure-toggle.js-toggle');
        if (measureToggle) {
            console.log("Found measure toggle button");
            
            // Create and dispatch a click event to properly trigger the leaflet control
            const clickEvent = new MouseEvent('click', {
                view: window,
                bubbles: true,
                cancelable: true
            });
            
            measureToggle.dispatchEvent(clickEvent);
            console.log("Dispatched click event to measure toggle");
            
            // Wait for the control to initialize
            setTimeout(() => {
                const measureInteraction = document.querySelector('.leaflet-control-measure-interaction.js-interaction');
                if (measureInteraction && measureInteraction.style.display !== 'none') {
                    console.log("Measurement interaction is visible");
                    
                    // Look for and click the start button
                    const startButton = document.querySelector('.js-start.start');
                    if (startButton) {
                        console.log("Found start button, clicking it");
                        const startClickEvent = new MouseEvent('click', {
                            view: window,
                            bubbles: true,
                            cancelable: true
                        });
                        startButton.dispatchEvent(startClickEvent);
                        
                        // Set button to active state after starting measurement
                        setTimeout(() => {
                            const isMeasuring = document.querySelector('.js-measuringprompt');
                            if (isMeasuring && isMeasuring.style.display !== 'none') {
                                setDrawingButtonState(true);
                            }
                        }, 100);
                    } else {
                        console.log("Start button not found");
                    }
                } else {
                    console.log("Measurement interaction not visible, trying manual approach");
                    // Fallback: manually show the interface
                    if (measureInteraction) {
                        measureInteraction.style.display = 'block';
                        const startPrompt = measureInteraction.querySelector('.js-startprompt.startprompt');
                        if (startPrompt) {
                            startPrompt.style.display = 'block';
                            setTimeout(() => {
                                const startBtn = startPrompt.querySelector('.js-start.start');
                                if (startBtn) {
                                    const startEvent = new MouseEvent('click', {
                                        view: window,
                                        bubbles: true,
                                        cancelable: true
                                    });
                                    startBtn.dispatchEvent(startEvent);
                                    
                                    // Set button to active state
                                    setTimeout(() => {
                                        const isMeasuring = document.querySelector('.js-measuringprompt');
                                        if (isMeasuring && isMeasuring.style.display !== 'none') {
                                            setDrawingButtonState(true);
                                        }
                                    }, 100);
                                }
                            }, 50);
                        }
                    }
                }
            }, 200);
            
        } else {
            console.log("Measure toggle button not found");
        }
    } catch (error) {
        console.error("Error in startMeasurement:", error);
    }
}

function setDrawingButtonState(isActive) {
    // Set the visual state of the drawing button
    const drawButton = document.getElementById('start-measurement-btn');
    if (drawButton) {
        if (isActive) {
            drawButton.classList.add('drawing-active');
            drawButton.textContent = 'Drawing Area...';
            console.log("Button set to active drawing state");
            // Start monitoring for measurement state changes
            startMeasurementMonitor();
        } else {
            drawButton.classList.remove('drawing-active');
            drawButton.textContent = 'Draw Analysis Area';
            console.log("Button set to inactive state");
            // Stop monitoring
            stopMeasurementMonitor();
        }
    }
}

let measurementMonitorInterval = null;
let measurementKeyListener = null;

function startMeasurementMonitor() {
    // Clear any existing monitor
    if (measurementMonitorInterval) {
        clearInterval(measurementMonitorInterval);
    }
    
    // Add escape key listener
    if (measurementKeyListener) {
        document.removeEventListener('keydown', measurementKeyListener);
    }
    
    measurementKeyListener = function(event) {
        if (event.key === 'Escape') {
            console.log("Escape key pressed during measurement, resetting button state");
            setTimeout(() => {
                setDrawingButtonState(false);
            }, 100);
        }
    };
    
    document.addEventListener('keydown', measurementKeyListener);
    
    // Monitor every 300ms to check if measurement is still active
    measurementMonitorInterval = setInterval(() => {
        const measuringPrompt = document.querySelector('.js-measuringprompt');
        const measureInteraction = document.querySelector('.leaflet-control-measure-interaction.js-interaction');
        
        // Check various conditions that indicate measurement is no longer active
        const isInteractionHidden = !measureInteraction || measureInteraction.style.display === 'none';
        const isMeasuringHidden = !measuringPrompt || measuringPrompt.style.display === 'none';
        const hasNoMeasureControl = !document.querySelector('.leaflet-control-measure');
        
        // If any of these conditions are true, measurement is no longer active
        if (isInteractionHidden || isMeasuringHidden || hasNoMeasureControl) {
            console.log("Measurement no longer active (monitor detected), resetting button state");
            setDrawingButtonState(false);
        }
    }, 300);
}

function stopMeasurementMonitor() {
    if (measurementMonitorInterval) {
        clearInterval(measurementMonitorInterval);
        measurementMonitorInterval = null;
    }
    
    if (measurementKeyListener) {
        document.removeEventListener('keydown', measurementKeyListener);
        measurementKeyListener = null;
    }
}

function autoDeleteMeasurement(e) {
    // Get coordinates first
    const coords = getAreaCoords(e);
    
    // Create a new observer for each measurement to handle multiple uses
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'childList') {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        // Look for the delete button in the newly added popup
                        const deleteButton = node.querySelector && node.querySelector('.js-deletemarkup');
                        if (deleteButton) {
                            console.log("Auto-clicking delete button (via MutationObserver)");
                            setTimeout(() => {
                                deleteButton.click();
                                observer.disconnect();
                                // Reset button state when measurement is completed
                                setDrawingButtonState(false);
                            }, 100); // Small delay to ensure popup is fully rendered
                        }
                        
                        // Also check if this node itself contains the popup structure
                        if (node.querySelector && node.querySelector('.leaflet-popup-content .js-deletemarkup')) {
                            const deleteBtn = node.querySelector('.leaflet-popup-content .js-deletemarkup');
                            console.log("Auto-clicking delete button (direct popup detection)");
                            setTimeout(() => {
                                deleteBtn.click();
                                observer.disconnect();
                                // Reset button state when measurement is completed
                                setDrawingButtonState(false);
                            }, 100);
                        }
                    }
                });
            }
        });
    });
    
    // Observe the document for popup changes
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // Also try direct search for existing popup (in case it's already there)
    setTimeout(() => {
        const existingDeleteButton = document.querySelector('.leaflet-popup-content .js-deletemarkup');
        if (existingDeleteButton) {
            console.log("Auto-clicking existing delete button");
            existingDeleteButton.click();
            observer.disconnect();
            // Reset button state when measurement is completed
            setDrawingButtonState(false);
        }
    }, 50);
    
    // Disconnect observer after 5 seconds to prevent memory leaks
    setTimeout(() => observer.disconnect(), 5000);
    
    return coords;
}

window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        getAreaCoords: getAreaCoords,
        autoDeleteMeasurement: autoDeleteMeasurement,
        startMeasurement: startMeasurement,
        handleMeasurementButton: handleMeasurementButton,
        setDrawingButtonState: setDrawingButtonState,
        startMeasurementMonitor: startMeasurementMonitor,
        stopMeasurementMonitor: stopMeasurementMonitor
    }
});

// Also make functions globally accessible
window.getAreaCoords = getAreaCoords;
window.autoDeleteMeasurement = autoDeleteMeasurement;
window.startMeasurement = startMeasurement;
window.handleMeasurementButton = handleMeasurementButton;
window.setDrawingButtonState = setDrawingButtonState;
window.startMeasurementMonitor = startMeasurementMonitor;
window.stopMeasurementMonitor = stopMeasurementMonitor;