// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
{% if enumerable %}import {ERC721Enumerable} from "@openzeppelin/contracts/token/ERC721/extensions/ERC721Enumerable.sol";{% endif %}
{% if uri_storage %}import {ERC721URIStorage} from "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";{% endif %}
{% if burnable %}import {ERC721Burnable} from "@openzeppelin/contracts/token/ERC721/extensions/ERC721Burnable.sol";{% endif %}
{% if ownable %}import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";{% endif %}

contract {{ CONTRACT_NAME }} is 
    ERC721{% if enumerable %}, ERC721Enumerable{% endif %}{% if uri_storage %}, ERC721URIStorage{% endif %}{% if burnable %}, ERC721Burnable{% endif %}{% if ownable %}, Ownable{% endif %} {
    
    {% if base_uri %}string private _baseTokenURI = "{{ base_uri }}";{% endif %}
    uint256 private _nextTokenId;

    constructor(
        {% if ownable %}address initialOwner{% endif %}
    )
        ERC721("{{ TOKEN_NAME }}", "{{ TOKEN_SYMBOL }}")
        {% if ownable %}Ownable(initialOwner){% endif %}
    {
        _nextTokenId = 1; // Start token IDs at 1
    }

    {% if mintable %}
    function safeMint(address to) public {% if ownable %}onlyOwner {% endif %}returns (uint256) {
        uint256 tokenId = _nextTokenId++;
        _safeMint(to, tokenId);
        return tokenId;
    }

    function safeMint(address to, uint256 tokenId) public {% if ownable %}onlyOwner {% endif %} {
        _safeMint(to, tokenId);
        if (tokenId >= _nextTokenId) {
            _nextTokenId = tokenId + 1;
        }
    }
    {% endif %}

    {% if uri_storage %}
    function setTokenURI(uint256 tokenId, string memory uri) public {% if ownable %}onlyOwner{% endif %} {
        _setTokenURI(tokenId, uri);
    }
    {% endif %}

    {% if base_uri %}
    function _baseURI() internal view override returns (string memory) {
        return _baseTokenURI;
    }

    {% if ownable %}
    function setBaseURI(string memory baseURI) public onlyOwner {
        _baseTokenURI = baseURI;
    }
    {% endif %}
    {% endif %}

    function nextTokenId() public view returns (uint256) {
        return _nextTokenId;
    }

    {% if enumerable and uri_storage %}
    // Override required by Solidity for multiple inheritance
    function tokenURI(uint256 tokenId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (string memory)
    {
        return super.tokenURI(tokenId);
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721, ERC721Enumerable, ERC721URIStorage)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }

    function _update(address to, uint256 tokenId, address auth)
        internal
        override(ERC721, ERC721Enumerable)
        returns (address)
    {
        return super._update(to, tokenId, auth);
    }

    function _increaseBalance(address account, uint128 value)
        internal
        override(ERC721, ERC721Enumerable)
    {
        super._increaseBalance(account, value);
    }
    {% elif enumerable %}
    // Override required by Solidity for ERC721Enumerable
    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721, ERC721Enumerable)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }

    function _update(address to, uint256 tokenId, address auth)
        internal
        override(ERC721, ERC721Enumerable)
        returns (address)
    {
        return super._update(to, tokenId, auth);
    }

    function _increaseBalance(address account, uint128 value)
        internal
        override(ERC721, ERC721Enumerable)
    {
        super._increaseBalance(account, value);
    }
    {% elif uri_storage %}
    // Override required by Solidity for ERC721URIStorage
    function tokenURI(uint256 tokenId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (string memory)
    {
        return super.tokenURI(tokenId);
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
    {% endif %}
}