// The archive only needs navigation and an image viewer. No network requests.
"use strict";
const english = document.documentElement.lang === "en";
const navigation = document.querySelector("nav");
function updateNavigation() {
    navigation?.classList.toggle("navbar-shrink", window.scrollY > 70);
}
window.addEventListener("scroll", updateNavigation, { passive: true });
updateNavigation();

document.querySelector(".navbar-toggle")?.addEventListener("click", (event) => {
    const button = event.currentTarget;
    const open = document.querySelector(".navbar-collapse").classList.toggle("in");
    button.setAttribute("aria-expanded", String(open));
});
document.querySelectorAll(".dropdown-toggle").forEach((toggle) => {
    toggle.addEventListener("click", (event) => {
        event.preventDefault();
        const parent = toggle.closest(".dropdown");
        const open = !parent.classList.contains("open");
        closeMenus();
        parent.classList.toggle("open", open);
        toggle.setAttribute("aria-expanded", String(open));
    });
});
function closeMenus() {
    document.querySelectorAll(".dropdown.open").forEach((menu) => {
        menu.classList.remove("open");
        menu.querySelector(".dropdown-toggle").setAttribute("aria-expanded", "false");
    });
}
document.addEventListener("click", (event) => {
    if (!event.target.closest(".dropdown")) closeMenus();
});
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMenus();
});

const images = [...document.querySelectorAll("a.fancybox")];
if (images.length && typeof HTMLDialogElement !== "undefined") {
    const viewer = document.createElement("dialog");
    viewer.className = "archive-lightbox";
    viewer.setAttribute("aria-label", english ? "Image viewer" : "Prohlížeč obrázků");
    viewer.innerHTML = '<button class="close-image" type="button">×</button>' +
        '<img alt=""><p></p><div class="image-controls">' +
        '<button type="button" class="previous-image">←</button>' +
        '<button type="button" class="next-image">→</button></div>';
    document.body.append(viewer);
    const picture = viewer.querySelector("img");
    const caption = viewer.querySelector("p");
    let group = [];
    let current = 0;
    function show(index) {
        current = (index + group.length) % group.length;
        picture.src = group[current].href;
        picture.alt = group[current].title || group[current].querySelector("img")?.alt || "";
        caption.textContent = picture.alt;
    }
    images.forEach((link) => link.addEventListener("click", (event) => {
        event.preventDefault();
        group = images.filter((item) => item.getAttribute("rel") === link.getAttribute("rel"));
        show(group.indexOf(link));
        viewer.showModal();
    }));
    const close = viewer.querySelector(".close-image");
    close.setAttribute("aria-label", english ? "Close" : "Zavřít");
    close.addEventListener("click", () => viewer.close());
    const previous = viewer.querySelector(".previous-image");
    previous.setAttribute("aria-label", english ? "Previous image" : "Předchozí obrázek");
    previous.addEventListener("click", () => show(current - 1));
    const next = viewer.querySelector(".next-image");
    next.setAttribute("aria-label", english ? "Next image" : "Další obrázek");
    next.addEventListener("click", () => show(current + 1));
    viewer.addEventListener("click", (event) => {
        const rect = viewer.getBoundingClientRect();
        if (event.target === viewer && (event.clientX < rect.left || event.clientX > rect.right ||
            event.clientY < rect.top || event.clientY > rect.bottom)) viewer.close();
    });
    viewer.addEventListener("keydown", (event) => {
        if (event.key === "ArrowLeft") { event.preventDefault(); show(current - 1); }
        if (event.key === "ArrowRight") { event.preventDefault(); show(current + 1); }
    });
}
