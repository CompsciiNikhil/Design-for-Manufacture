from step_parser import StepParser
from topology import TopologyExtractor
from mold_direction import MoldDirectionAnalyzer
from draft_analysis import DraftAnalyzer
from undercut_detector import UndercutDetector
from core_cavity import CoreCavityClassifier
from parting_line import PartingLineExtractor
from edge_extractor import EdgeExtractor
from visualizer import PartVisualizer
from silhouette_detector import (
    SilhouetteDetector
)
from parting_line_v2 import (
    PartingLineV2
)

def main():

    parser = StepParser("Part1.stp")

    part = parser.parse()

    topology = TopologyExtractor(part.shape)

    graph = topology.build_adjacency_graph()
    analyzer = MoldDirectionAnalyzer(part)

    best_direction, best_score = (
        analyzer.find_best_direction()
    )

    silhouette_detector = (
        SilhouetteDetector(part)
    )

    silhouette_results = (
        silhouette_detector.detect(
            best_direction
        )
    )

    parting_v2 = (
        PartingLineV2(
            graph,
            silhouette_results["faces"]
        )
    )

    v2_pairs = (
        parting_v2.extract_boundary_pairs()
    )

    print(
        "\n----- PARTING LINE V2 -----"
    )

    print(
        f"Boundary Pairs: "
        f"{len(v2_pairs)}"
    )

    print(
        f"First 10: "
        f"{v2_pairs[:10]}"
    )

    print(
        "\n----- SILHOUETTE -----"
    )

    print(
        f"Silhouette Faces: "
        f"{silhouette_results['count']}"
    )

    print(
        f"Silhouette Area: "
        f"{silhouette_results['area']:.3f}"
    )

    classifier = CoreCavityClassifier(part)

    classification = classifier.classify(
        best_direction
    )

    parting = PartingLineExtractor(
        graph,
        classification
    )

    candidates = (
        parting.extract_candidates()
    )

    face_map = topology.get_face_map()

    edge_extractor = EdgeExtractor(
        face_map
    )

    shared_edges_v2 = (
        edge_extractor.extract_shared_edges(
            v2_pairs
        )
    )

    print(
        "\n----- SHARED EDGES -----"
    )

    print(
        f"Shared Edges: "
        f"{len(shared_edges_v2)}"
    )

    print(
        "\n----- PARTING LINE -----"
    )

    print(
        f"Boundary Pairs: "
        f"{len(candidates)}"
    )

    print(
        f"First 10: "
        f"{candidates[:10]}"
    )

    print("\n----- CORE / CAVITY -----")

    print(
        f"Core Faces: "
        f"{classification['core_count']}"
    )

    print(
        f"Cavity Faces: "
        f"{classification['cavity_count']}"
    )

    print(
        f"Neutral Faces: "
        f"{classification['neutral_count']}"
    )


    undercut_detector = (
        UndercutDetector(part)
    )

    undercut_results = (
        undercut_detector.analyze(
            best_direction
        )
    )

    print("\n----- UNDERCUT ANALYSIS -----")

    print(
        f"Undercut Faces: "
        f"{undercut_results['undercut_count']}"
    )

    print(
        f"Undercut Area: "
        f"{undercut_results['undercut_area']:.3f}"
    )

    draft_analyzer = DraftAnalyzer(part)

    draft_results = (
        draft_analyzer.analyze_direction(
            best_direction
        )
    )

    draft_angles = [
        item["draft_angle"]
        for item in draft_results
        if item["draft_angle"] is not None
    ]

    print("\n----- DRAFT ANALYSIS -----")

    print(
        f"Faces Analyzed: "
        f"{len(draft_angles)}"
    )

    print(
        f"Minimum Draft: "
        f"{min(draft_angles):.3f}"
    )

    print(
        f"Maximum Draft: "
        f"{max(draft_angles):.3f}"
    )

    print(
        f"Average Draft: "
        f"{sum(draft_angles)/len(draft_angles):.3f}"
    )

    print("\n----- MOLD DIRECTION -----")

    print(
        f"Direction: {best_direction}"
    )

    print(
        f"Score: {best_score:.3f}"
    )

    print("\n----- TOPOLOGY -----")

    print(
        f"Face 0 Neighbors: "
        f"{graph.get(0, [])}"
    )

    print("\n----- SUMMARY -----")

    print(
        f"Total Faces: {len(part.faces)}"
    )

    if len(part.faces) > 0:

        first_face = part.faces[0]

        print("\nFirst Face:")

        print(
            f"ID: {first_face.face_id}"
        )

        print(
            f"Type: {first_face.surface_type}"
        )

        print(
            f"Area: {first_face.area:.3f}"
        )

        print(
            f"Centroid: {first_face.centroid}"
        )

        print(
            f"Normal: {first_face.normal}"
        )
    visualizer = PartVisualizer()

    visualizer.show_part(
        part.shape
    )

    visualizer.show_silhouette_faces(
        face_map,
        silhouette_results["faces"]
    )

    visualizer.show_edges(
        shared_edges_v2
    )

    visualizer.run()


if __name__ == "__main__":
    main()