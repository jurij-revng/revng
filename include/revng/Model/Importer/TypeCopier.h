#pragma once

//
// This file is distributed under the MIT License. See LICENSE.md for details.
//

#include "llvm/ADT/DenseSet.h"
#include "llvm/ADT/DepthFirstIterator.h"

#include "revng/ADT/GenericGraph.h"
#include "revng/Model/Binary.h"

template<typename T>
concept HasCustomAndOriginalName = requires(const T &Element) {
  { Element.CustomName() } -> std::same_as<const model::Identifier &>;
  { Element.OriginalName() } -> std::same_as<const std::string &>;
};
static_assert(HasCustomAndOriginalName<model::TypeDefinition>);
static_assert(HasCustomAndOriginalName<model::EnumEntry>);

class TypeCopier {
private:
  TupleTree<model::Binary> &FromModel;
  TupleTree<model::Binary> &DestinationModel;

  // Track the copied types so we can fixup references later on
  llvm::DenseMap<uint64_t, uint64_t> AlreadyCopied;
  llvm::DenseSet<model::TypeDefinition *> NewTypes;

  struct NodeData {
    const model::UpcastableTypeDefinition *T;
  };
  using Node = ForwardNode<NodeData>;
  using Graph = GenericGraph<Node>;
  std::optional<Graph> TypeGraph;
  std::map<const model::TypeDefinition *, Node *> TypeToNode;
  bool Finalized = false;

public:
  TypeCopier(TupleTree<model::Binary> &FromModel,
             TupleTree<model::Binary> &DestinationModel) :
    FromModel(FromModel), DestinationModel(DestinationModel) {}
  ~TypeCopier() { revng_assert(Finalized); }

  model::UpcastableType copyTypeInto(const model::TypeDefinition &Definition) {
    ensureGraph();

    model::UpcastableType Result;
    llvm::df_iterator_default_set<Node *> Visited;
    for (Node *N : depth_first_ext(TypeToNode.at(&Definition), Visited))
      ;

    for (const auto &P : FromModel->TypeDefinitions()) {
      if (AlreadyCopied.count(P.get()->ID()) == 0
          && Visited.contains(TypeToNode.at(P.get()))) {
        // Clone the type
        model::UpcastableTypeDefinition NewType = P;

        // Reset type ID: recordNewType will set it for us
        NewType->ID() = 0;

        // Adjust all CustomNames
        auto Visitor = [](auto &Element) {
          using T = std::decay_t<decltype(Element)>;
          if constexpr (HasCustomAndOriginalName<T>) {
            std::string CustomName = Element.CustomName().str().str();
            Element.CustomName() = model::Identifier();
            if (Element.OriginalName().empty())
              Element.OriginalName() = CustomName;
          }
        };
        visitTupleTree(NewType, Visitor, [](const auto &) {});

        // Record the type
        auto [Def, Type] = DestinationModel->recordNewType(std::move(NewType));
        NewTypes.insert(&Def);
        auto [_, Success] = AlreadyCopied.insert({ P->ID(), Def.ID() });
        revng_assert(Success);

        // Record the type we were looking for originally
        if (P->key() == Definition.key())
          Result = std::move(Type);
      }
    }

    // TODO: consider fixing only the necessary references
    DestinationModel.initializeReferences();

    return Result;
  }

  void finalize() {
    revng_assert(not Finalized);
    Finalized = true;

    // Visit all references into the newly created types and remap them
    // according to the map
    auto Visitor = [this](auto &Element) {
      using T = std::decay_t<decltype(Element)>;
      if constexpr (std::is_same_v<T, model::DefinitionReference>) {
        model::DefinitionReference &Path = Element;
        if (Path.empty())
          return;

        // Extract ID from the key
        const TupleTreeKeyWrapper &TypeKey = Path.path().toArrayRef()[1];
        auto [ID, Kind] = *TypeKey.tryGet<model::TypeDefinition::Key>();
        revng_assert(AlreadyCopied.count(ID) == 1);
        model::TypeDefinition::Key Key = { AlreadyCopied[ID], Kind };
        Path = DestinationModel->getDefinitionReference(Key);
      }
    };

    for (model::TypeDefinition *NewType : NewTypes)
      visitTupleTree(NewType, Visitor, [](const auto &) {});
  }

private:
  void ensureGraph() {
    if (!TypeGraph) {
      TypeGraph = Graph();
      for (model::UpcastableTypeDefinition &T : FromModel->TypeDefinitions())
        TypeToNode[T.get()] = TypeGraph->addNode(NodeData{ &T });

      // Create type system edges
      for (model::UpcastableTypeDefinition &T : FromModel->TypeDefinitions())
        for (const model::Type *EdgeType : T->edges())
          if (const auto *Definition = EdgeType->skipToDefinition())
            TypeToNode.at(T.get())->addSuccessor(TypeToNode.at(Definition));
    }
  }
};
