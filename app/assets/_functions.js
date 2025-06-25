console.log("functions.js loaded!");

function getAreaCoords(e) {
    if (e && Array.isArray(e.points)) {
        // Map each point to [lat, lng]
        const coords = e.points.map(pt => [pt.lng, pt.lat]);
        console.log("coords", coords);
        return {coordinates: coords};
    }

    return {coordinates: []};
}

window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        getAreaCoords: getAreaCoords
    }
});